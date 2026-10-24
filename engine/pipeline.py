"""
CV Pipeline — Главный координатор видеоаналитики LinQ Safety Guard.
Связывает воедино детекцию (HAL), трекинг во времени (ByteTrack), движок правил (Shapely),
дедупликацию (Anti-Spam), визуализацию оверлеев и сохранение доказательств в хранилище (Storage Layer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import math
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
import cv2
import numpy as np

from app.storage.base import BaseStorageProvider
from app.storage.factory import get_storage_provider
from engine.deduplication.anti_spam import AntiSpamEngine
from engine.deduplication.types import ConfirmedIncident
from engine.inference.base import BaseInferenceEngine, Detection, InferenceMetrics
from engine.inference.factory import create_inference_engine
from engine.rules.base import FrameContext, RuleViolation, ViolationSeverity
from engine.rules.engine import RulesEngine
from engine.rules.danger_zone import DangerZoneRule
from engine.rules.proximity import ProximityRule
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.tracking.tracker import ByteTracker
from engine.tracking.types import TrackedObject


@dataclass
class PipelineMetrics:
    """Метрики сквозной производительности конвейера видеоаналитики."""
    inference_time_ms: float = 0.0
    tracking_time_ms: float = 0.0
    rules_time_ms: float = 0.0
    total_time_ms: float = 0.0
    fps: float = 0.0
    frames_processed: int = 0
    incidents_total: int = 0
    backend_name: str = ""


@dataclass
class FrameProcessingResult:
    """Полный результат обработки единичного кадра."""
    frame_id: int
    timestamp: float
    camera_id: str
    annotated_frame: np.ndarray
    detections: List[Detection]
    tracked_objects: List[TrackedObject]
    raw_violations: List[RuleViolation]
    new_incidents: List[ConfirmedIncident]
    active_incidents: List[ConfirmedIncident]
    metrics: PipelineMetrics


class CVPipeline:
    """
    Высокопроизводительный конвейер компьютерного зрения для мониторинга безопасности цеха.
    """

    def __init__(
        self,
        inference_engine: Optional[BaseInferenceEngine] = None,
        tracker: Optional[ByteTracker] = None,
        rules_engine: Optional[RulesEngine] = None,
        anti_spam_engine: Optional[AntiSpamEngine] = None,
        storage_provider: Optional[BaseStorageProvider] = None,
        incident_callback: Optional[Callable[[ConfirmedIncident, np.ndarray], None]] = None,
        camera_id: str = "camera_01",
    ) -> None:
        self.camera_id = camera_id
        self.inference_engine = inference_engine or create_inference_engine()
        self.tracker = tracker or ByteTracker()
        self.rules_engine = rules_engine or self._create_default_rules_engine()
        self.anti_spam = anti_spam_engine or AntiSpamEngine()
        self.storage = storage_provider or get_storage_provider()
        self.incident_callback = incident_callback

        self.frames_processed = 0
        self.incidents_total = 0
        self._last_fps = 0.0

    @staticmethod
    def _create_default_rules_engine() -> RulesEngine:
        """Создает стандартный набор правил ТБ по умолчанию."""
        engine = RulesEngine()
        engine.add_rule(DangerZoneRule())
        engine.add_rule(ProximityRule(safe_distance_px=140.0))
        engine.add_rule(FallDetectionRule())
        engine.add_rule(PPEComplianceRule(require_helmet=True, require_vest=True))
        return engine

    def process_frame(
        self,
        frame: np.ndarray,
        frame_id: Optional[int] = None,
        timestamp: Optional[float] = None,
        camera_id: Optional[str] = None,
        render_annotations: bool = True,
        source_fps: float = 25.0,
    ) -> FrameProcessingResult:
        """
        Полная обработка кадра: инференс -> трекинг -> правила -> дедупликация -> сохранение снапшота.
        """
        t_start = time.perf_counter()
        self.frames_processed += 1
        fid = frame_id if frame_id is not None else self.frames_processed
        ts = timestamp if timestamp is not None else time.time()
        cam_id = camera_id or self.camera_id

        orig_h, orig_w = frame.shape[:2]

        # 1. Инференс на чипе LinQ TPU или ONNX CPU
        t_inf_start = time.perf_counter()
        inf_result = self.inference_engine.infer(frame)
        t_inf_end = time.perf_counter()
        detections = inf_result.detections

        # 2. Пространственно-временной трекинг (ByteTrack)
        t_track_start = time.perf_counter()
        tracked_objects = self.tracker.update(detections)
        t_track_end = time.perf_counter()

        # 3. Движок правил ТБ
        t_rules_start = time.perf_counter()
        context = FrameContext(
            frame_id=fid,
            timestamp=ts,
            camera_id=cam_id,
            frame_width=orig_w,
            frame_height=orig_h,
            fps=source_fps if math.isfinite(source_fps) and source_fps > 0 else 25.0,
            all_detections=detections,
        )
        raw_violations = self.rules_engine.evaluate(tracked_objects, context)
        t_rules_end = time.perf_counter()

        # 4. Дедупликация и подавление ложных тревог (Anti-Spam)
        new_incidents, active_incidents = self.anti_spam.process(raw_violations, context)

        # 5. Отрисовка оверлеев и аннотаций
        annotated_frame = (
            self.render_overlay(frame, tracked_objects, raw_violations, active_incidents)
            if render_annotations
            else frame
        )

        # 6. Сохранение снапшотов инцидентов в Storage Layer
        if new_incidents:
            self.incidents_total += len(new_incidents)
            for incident in new_incidents:
                try:
                    snapshot_url = self.storage.save_snapshot(
                        image_data=annotated_frame,
                        incident_id=incident.incident_id,
                        camera_id=cam_id,
                    )
                    incident.snapshot_path = snapshot_url
                except Exception as e:
                    print(f"[CVPipeline] Ошибка сохранения стоп-кадра {incident.incident_id}: {e}")

                if self.incident_callback:
                    try:
                        self.incident_callback(incident, annotated_frame)
                    except Exception as cb_err:
                        raise RuntimeError(f"Cannot persist or deliver incident {incident.incident_id}") from cb_err

        # Замеры времени
        t_end = time.perf_counter()
        tot_ms = (t_end - t_start) * 1000.0
        fps = 1000.0 / tot_ms if tot_ms > 0 else 0.0
        self._last_fps = fps

        metrics = PipelineMetrics(
            inference_time_ms=round((t_inf_end - t_inf_start) * 1000.0, 2),
            tracking_time_ms=round((t_track_end - t_track_start) * 1000.0, 2),
            rules_time_ms=round((t_rules_end - t_rules_start) * 1000.0, 2),
            total_time_ms=round(tot_ms, 2),
            fps=round(fps, 1),
            frames_processed=self.frames_processed,
            incidents_total=self.incidents_total,
            backend_name=inf_result.metrics.backend_name,
        )

        return FrameProcessingResult(
            frame_id=fid,
            timestamp=ts,
            camera_id=cam_id,
            annotated_frame=annotated_frame,
            detections=detections,
            tracked_objects=tracked_objects,
            raw_violations=raw_violations,
            new_incidents=new_incidents,
            active_incidents=active_incidents,
            metrics=metrics,
        )

    def render_overlay(
        self,
        frame: np.ndarray,
        tracks: List[TrackedObject],
        violations: List[RuleViolation],
        active_incidents: List[ConfirmedIncident],
    ) -> np.ndarray:
        """
        Профессиональная отрисовка оверлея с цветовой дифференциацией нарушителей и зон.
        """
        canvas = frame.copy()
        violating_track_ids = {v.track_id for v in violations}
        violating_track_ids.update({inc.track_id for inc in active_incidents})

        # 1. Отрисовка полигонов опасных зон (если есть DangerZoneRule)
        dz_rule = self.rules_engine.get_rule("danger_zone")
        if dz_rule and isinstance(dz_rule, DangerZoneRule) and dz_rule.zones:
            overlay = canvas.copy()
            for zone in dz_rule.zones.values():
                pts = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
                # Полупрозрачная заливка зоны красным цветом
                cv2.fillPoly(overlay, [pts], (0, 0, 180))
                # Контур зоны
                cv2.polylines(canvas, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
                # Подпись зоны
                first_pt = zone.polygon[0]
                cv2.putText(
                    canvas,
                    f"ZONE: {zone.name}",
                    (int(first_pt[0]), max(20, int(first_pt[1]) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 0, 255),
                    2,
                )
            # Смешивание с альфа-каналом (30% прозрачности)
            cv2.addWeighted(overlay, 0.25, canvas, 0.75, 0, canvas)

        # 2. Отрисовка объектов и треков
        for track in tracks:
            x1, y1, x2, y2 = track.bbox.as_int_xyxy()
            is_violator = track.track_id in violating_track_ids

            if is_violator:
                color = (0, 0, 235)  # Ярко-красный для нарушителей
                border_th = 3
            elif track.class_name == "forklift":
                color = (255, 165, 0)  # Оранжевый для погрузчиков
                border_th = 2
            else:
                color = (0, 200, 0)  # Зеленый для персонала без нарушений
                border_th = 2

            # Рамка объекта
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, border_th)

            # Плашка с информацией (ID, класс, скорость)
            label = f"#{track.track_id} {track.class_name}"
            if track.speed > 0.5:
                label += f" | {track.speed:.1f}px/f"

            (txt_w, txt_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(canvas, (x1, y1 - txt_h - 6), (x1 + txt_w + 6, y1), color, -1)
            cv2.putText(
                canvas,
                label,
                (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # Точка стоп и траектория
            foot_x, foot_y = int(round(track.bottom_center[0])), int(round(track.bottom_center[1]))
            cv2.circle(canvas, (foot_x, foot_y), 4, color, -1)

            # Отрисовка хвоста траектории
            if len(track.history) > 1:
                hist_pts = np.array(track.history[-15:], dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(canvas, [hist_pts], isClosed=False, color=color, thickness=1)

        # 3. Информационный статус-бар вверху кадра
        active_count = len(active_incidents)
        bar_color = (0, 0, 180) if active_count > 0 else (40, 40, 40)
        cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 32), bar_color, -1)

        status_text = (
            f"LinQ Safety Guard | Cam: {self.camera_id} | Objects: {len(tracks)} | "
            f"Violations: {active_count} | FPS: {self._last_fps:.1f} ({self.inference_engine.__class__.__name__})"
        )
        cv2.putText(
            canvas,
            status_text,
            (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        return canvas

    def process_video_file(
        self,
        video_path: str,
        max_frames: Optional[int] = None,
        target_fps: Optional[float] = None,
    ) -> Iterator[FrameProcessingResult]:
        """
        Генератор покадровой обработки видеофайла или потока RTSP.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Видеофайл {video_path} не найден.")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Не удалось открыть видеофайл {video_path}.")

        frame_count = 0
        prev_time = time.perf_counter()
        media_fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(media_fps) or media_fps <= 0:
            media_fps = 25.0
        epoch_start = time.time()

        try:
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                frame_count += 1
                if max_frames and frame_count > max_frames:
                    break

                # Ограничение FPS при необходимости
                if target_fps and target_fps > 0:
                    desired_interval = 1.0 / target_fps
                    elapsed = time.perf_counter() - prev_time
                    if elapsed < desired_interval:
                        time.sleep(desired_interval - elapsed)
                    prev_time = time.perf_counter()

                result = self.process_frame(
                    frame=frame,
                    frame_id=frame_count,
                    timestamp=epoch_start + (frame_count - 1) / media_fps,
                    source_fps=media_fps,
                )
                yield result
        finally:
            cap.release()

    def reset(self) -> None:
        """Сброс внутренних состояний трекера, правил и дедупликатора."""
        self.tracker.reset()
        self.anti_spam.reset()
        self.rules_engine.reset()
        self.frames_processed = 0
        self.incidents_total = 0
        self._last_fps = 0.0
