"""Inference pipelines for cameras captured by an operator's browser."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict

import cv2
import numpy as np

from app.config import BASE_DIR, settings
from app.db.models.camera import Camera
from app.db.session import SessionLocal
from app.schemas.incident import IncidentCreate
from app.services.camera_hub import camera_hub
from app.services.incident_service import create_or_merge_incident
from app.services.notifications import notification_manager
from app.services.notifier import notifier
from app.storage.factory import get_storage_provider
from engine.deduplication.anti_spam import AntiSpamEngine
from engine.incident_client import IncidentClient
from engine.inference.factory import create_inference_engine
from engine.pipeline import CVPipeline
from engine.rules.engine import RulesEngine
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.registry import get_incident_presentation

log = logging.getLogger(__name__)

_lock = threading.RLock()
_pipelines: Dict[str, CVPipeline] = {}
_frame_ids: Dict[str, int] = {}
_sink: IncidentClient | None = None


class BrowserCameraConfigurationError(RuntimeError):
    """The configured inference backend cannot process browser camera frames."""


def _get_sink() -> IncidentClient:
    global _sink
    if _sink is None:
        outbox = BASE_DIR / "storage" / "browser_camera_outbox"
        api_url = f"http://127.0.0.1:{settings.PORT}{settings.API_V1_PREFIX}"
        _sink = IncidentClient(api_url, outbox)
        _sink.start()
    return _sink


def _handle_browser_incident(incident, frame_bgr: np.ndarray, camera_info: dict, sink: IncidentClient) -> None:
    camera_id = camera_info["camera_id"]
    try:
        # 1. Запоминаем стоп-кадр нарушения в CameraHub для живого отображения в интерфейсе и вкладке 'Светофор'
        camera_hub.set_violation_frame(camera_id, frame_bgr)

        # 2. Сохраняем снимок в хранилище (локальное / S3)
        storage = get_storage_provider()
        key = storage.save_snapshot_key(frame_bgr, incident.incident_id, camera_id)
        snapshot_url = storage.get_snapshot_url(key)
        incident.snapshot_path = snapshot_url

        # 3. Формируем запись инцидента
        h, w = frame_bgr.shape[:2]
        bbox_box = None
        if incident.bbox:
            cb = incident.bbox.clip(w, h)
            bbox_box = [cb.x1 / w * 100, cb.y1 / h * 100, cb.width / w * 100, cb.height / h * 100]

        raw_sev = getattr(incident.severity, "value", str(incident.severity)).upper()
        norm_severity = {"CRITICAL": "critical", "HIGH": "warning", "MEDIUM": "warning", "LOW": "info"}.get(
            raw_sev, "warning"
        )
        ppe = incident.metadata.get("ppe_type")
        event_type = f"no_{ppe}" if ppe else incident.rule_name
        presentation = get_incident_presentation(incident.rule_name, incident.metadata)
        title = presentation.title or "Сотрудник без каски"
        action = presentation.action or "Оповестите мастера участка для проведения целевого инструктажа."

        incident_in = IncidentCreate(
            id=incident.incident_id,
            site_id=camera_info["site_id"],
            camera_id=camera_id,
            zone=incident.zone_id or camera_info.get("zone", "Цех № 1"),
            title=title,
            time=datetime.now().strftime("%H:%M:%S"),
            severity=norm_severity,
            type="person",
            description=incident.description or title,
            action=action,
            image_key=key,
            status="new",
            box=bbox_box,
            track_id=incident.track_id,
            employee_name=f"Сотрудник #{incident.track_id}" if incident.track_id else "Оператор камеры",
            employee_role=f"Сотрудник · {camera_info.get('zone', 'Цех № 1')}",
            employee_number=f"00{incident.track_id:03d}" if incident.track_id else "00101",
            employee_access="Доступ разрешён · СКУД",
            contact_name="Мастер смены",
            contact_role="Дежурный инженер",
            contact_radio="Канал 1",
            contact_phone="+7 (495) 123-45-67",
        )

        with SessionLocal() as db:
            inc_read, created = create_or_merge_incident(db, incident_in, storage)
            inc_data = inc_read.model_dump(mode="json")

            # 4. Рассылка события в WebSocket для живого обновления журнала и карточек
            notifier.broadcast_sync({
                "event": "INCIDENT_CREATED" if created else "INCIDENT_UPDATED",
                "data": inc_data,
            })

            # 5. Мгновенная отправка оповещения (Telegram, сирена и внешние адаптеры)
            if created:
                notification_manager.dispatch_incident(inc_data, snapshot_url)
                log.info(
                    "[%s] Оповещение о нарушении на подключенной камере отправлено в Telegram/WebSocket (id=%s, title='%s')",
                    camera_id, incident.incident_id, title
                )
            else:
                notification_manager.refresh_incident(inc_data)
    except Exception as err:
        log.exception("[%s] Ошибка прямой отправки оповещения с подключенной камеры: %s", camera_id, err)

    # Резервная отправка в outbox клиент
    try:
        sink.submit(incident, frame_bgr, camera_info)
    except Exception as err:
        log.debug("[%s] Outbox sink submit fallback info: %s", camera_id, err)


def _get_pipeline(camera: Camera) -> CVPipeline:
    if settings.INFERENCE_BACKEND.upper() == "LINQ_TPU":
        raise BrowserCameraConfigurationError(
            "Захват из браузера сейчас несовместим с параллельным TPU-воркером. "
            "Для этого режима установите INFERENCE_BACKEND=ONNX_CPU."
        )
    if settings.INFERENCE_BACKEND.upper() != "ONNX_CPU":
        raise BrowserCameraConfigurationError(
            "Для реальной камеры требуется INFERENCE_BACKEND=ONNX_CPU; MOCK не выполняет детекцию."
        )

    pipeline = _pipelines.get(camera.id)
    if pipeline is not None:
        return pipeline

    model_path = Path(settings.ONNX_MODEL_PATH)
    if not model_path.is_absolute():
        model_path = BASE_DIR / model_path
    try:
        inference = create_inference_engine(
            backend="ONNX_CPU",
            model_path=str(model_path),
            conf_threshold=settings.CONFIDENCE_THRESHOLD,
            iou_threshold=settings.IOU_THRESHOLD,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise BrowserCameraConfigurationError(
            f"Не удалось загрузить ONNX-модель для камеры: {exc}"
        ) from exc
    classes = set(inference.class_names.values())
    if "person" not in classes or not classes.intersection({"helmet", "no_helmet"}):
        inference.close()
        raise BrowserCameraConfigurationError(
            "ONNX-модель должна содержать классы person и helmet либо no_helmet."
        )

    sink = _get_sink()
    camera_info = {
        "camera_id": camera.id,
        "site_id": camera.site_id,
        "zone": camera.zone,
    }
    rules = RulesEngine([PPEComplianceRule(require_helmet=True, require_vest=False)])
    debounce_frames = max(2, min(int(getattr(settings, "DEBOUNCE_FRAMES", 15)), 3))
    cooldown_seconds = float(getattr(settings, "COOLDOWN_SECONDS", 20.0))
    pipeline = CVPipeline(
        inference_engine=inference,
        rules_engine=rules,
        anti_spam_engine=AntiSpamEngine(
            debounce_frames=debounce_frames,
            cooldown_seconds=cooldown_seconds,
        ),
        incident_callback=lambda incident, frame: _handle_browser_incident(incident, frame, camera_info, sink),
        camera_id=camera.id,
    )
    _pipelines[camera.id] = pipeline
    _frame_ids[camera.id] = 0
    log.info("Browser camera inference initialized camera=%s backend=ONNX_CPU debounce=%d", camera.id, debounce_frames)
    return pipeline


def process_browser_frame(camera: Camera, jpeg: bytes) -> dict:
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Не удалось прочитать JPEG-кадр.")
    if image.shape[1] > 1920 or image.shape[0] > 1080:
        raise ValueError("Разрешение кадра не должно превышать 1920×1080.")

    # Обновляем живой кадр в CameraHub
    camera_hub.set_frame(camera.id, image)

    with _lock:
        pipeline = _get_pipeline(camera)
        _frame_ids[camera.id] += 1
        result = pipeline.process_frame(
            image,
            frame_id=_frame_ids[camera.id],
            camera_id=camera.id,
            render_annotations=False,
        )
        if result.raw_violations:
            camera_hub.set_violation_frame(camera.id, image)
        detections = [
            {
                "class_name": detection.class_name,
                "confidence": round(detection.confidence, 3),
                "bbox": list(detection.bbox.as_xyxy()),
            }
            for detection in result.detections
        ]
        return {
            "camera_id": camera.id,
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
            "detections": detections,
            "violations": [
                {
                    "description": violation.description,
                    "class_name": violation.metadata.get("ppe_type", "ppe"),
                    "bbox": list(violation.bbox.as_xyxy()),
                }
                for violation in result.raw_violations
            ],
            "new_incidents": [incident.description for incident in result.new_incidents],
            "metrics": {
                "backend": result.metrics.backend_name,
                "inference_ms": result.metrics.inference_time_ms,
                "fps": result.metrics.fps,
            },
        }


def close_browser_camera_pipelines() -> None:
    global _sink
    with _lock:
        for pipeline in _pipelines.values():
            pipeline.inference_engine.close()
        _pipelines.clear()
        _frame_ids.clear()
        if _sink is not None:
            _sink.close()
            _sink = None
