"""
ByteTrack — Алгоритм многообъектного трекинга во времени (Multi-Object Tracking).
Ассоциация на базе двухуровневого сопоставления детекций высокой и низкой уверенности.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import numpy as np

from engine.inference.base import BoundingBox, Detection
from engine.tracking.kalman import KalmanBoxTracker
from engine.tracking.types import TrackState, TrackedObject


class STrack:
    """Внутреннее представление сопровождаемого трека в трекере."""

    def __init__(self, detection: Detection, track_id: int) -> None:
        self.track_id = track_id
        self.class_id = detection.class_id
        self.class_name = detection.class_name
        self.confidence = detection.confidence

        self.kalman = KalmanBoxTracker(detection.bbox.as_xyxy())
        self.state = TrackState.NEW
        self.is_confirmed = False

        self.age = 1
        self.hits = 1
        self.time_since_update = 0
        self.history: List[Tuple[float, float]] = [detection.bbox.bottom_center]

        self.last_bbox = detection.bbox

    def predict(self) -> Tuple[float, float, float, float]:
        pred_box = self.kalman.predict()
        self.age += 1
        self.time_since_update += 1
        return pred_box

    def update(self, detection: Detection) -> None:
        self.kalman.update(detection.bbox.as_xyxy())
        self.last_bbox = detection.bbox
        self.confidence = detection.confidence
        self.class_id = detection.class_id
        self.class_name = detection.class_name

        self.hits += 1
        self.time_since_update = 0

        # Сохраняем историю положения стоп (до 100 точек)
        foot = detection.bbox.bottom_center
        self.history.append(foot)
        if len(self.history) > 100:
            self.history.pop(0)

        if self.state == TrackState.NEW and self.hits >= 2:
            self.state = TrackState.TRACKED
            self.is_confirmed = True
        elif self.state == TrackState.LOST:
            self.state = TrackState.TRACKED

    def mark_lost(self) -> None:
        self.state = TrackState.LOST

    def mark_removed(self) -> None:
        self.state = TrackState.REMOVED

    def to_tracked_object(self) -> TrackedObject:
        current_xyxy = self.kalman.get_state()
        bbox = BoundingBox(*current_xyxy)
        vx, vy = self.kalman.get_velocity()
        speed = math.sqrt(vx * vx + vy * vy)

        return TrackedObject(
            track_id=self.track_id,
            class_id=self.class_id,
            class_name=self.class_name,
            bbox=bbox,
            confidence=self.confidence,
            state=self.state,
            age=self.age,
            hits=self.hits,
            time_since_update=self.time_since_update,
            velocity=(vx, vy),
            speed=speed,
            history=list(self.history),
            is_confirmed=self.is_confirmed,
        )


class ByteTracker:
    """
    Промышленная реализация алгоритма ByteTrack для задач промышленной безопасности.
    """

    def __init__(
        self,
        high_thresh: float = 0.45,
        low_thresh: float = 0.15,
        match_thresh_high: float = 0.75,  # Порог стоимости IoU (1 - IoU) для первого уровня
        match_thresh_low: float = 0.50,   # Порог стоимости IoU для второго уровня
        max_lost_frames: int = 30,
        min_hits_to_confirm: int = 2,
    ) -> None:
        self.high_thresh = high_thresh
        self.low_thresh = low_thresh
        self.match_thresh_high = match_thresh_high
        self.match_thresh_low = match_thresh_low
        self.max_lost_frames = max_lost_frames
        self.min_hits_to_confirm = min_hits_to_confirm

        self.tracked_stracks: List[STrack] = []  # Активные подтвержденные треки
        self.lost_stracks: List[STrack] = []     # Временно потерянные треки
        self.unconfirmed_stracks: List[STrack] = []  # Новые неподтвержденные треки

        self.frame_id: int = 0
        self._next_id: int = 1

    def _get_next_id(self) -> int:
        cur = self._next_id
        self._next_id += 1
        return cur

    def update(self, detections: List[Detection]) -> List[TrackedObject]:
        """
        Обновление трекера новым набором детекций текущего кадра.
        :param detections: список детекций от детектора
        :return: список активных сопровождаемых объектов TrackedObject
        """
        self.frame_id += 1

        # 1. Разделение детекций на высоко- и низкоуверенные
        dets_high: List[Detection] = []
        dets_low: List[Detection] = []

        for d in detections:
            if d.confidence >= self.high_thresh:
                dets_high.append(d)
            elif d.confidence >= self.low_thresh:
                dets_low.append(d)

        # 2. Предсказание положения всех существующих треков через фильтр Калмана
        all_active_tracks = self.tracked_stracks + self.unconfirmed_stracks
        for track in all_active_tracks:
            track.predict()
        for track in self.lost_stracks:
            track.predict()

        # 3. Первый этап ассоциации: сопоставление high-conf детекций с активными треками
        matched_a, unmatched_tracks_a, unmatched_dets_high = self._associate(
            all_active_tracks, dets_high, self.match_thresh_high
        )

        for track_idx, det_idx in matched_a:
            all_active_tracks[track_idx].update(dets_high[det_idx])

        # 4. Второй этап ассоциации: сопоставление оставшихся треков с low-conf детекциями
        # Отбираем только подтвержденные треки среди оставшихся
        candidates_for_low = [
            all_active_tracks[i] for i in unmatched_tracks_a if all_active_tracks[i].state == TrackState.TRACKED
        ]

        matched_b, unmatched_tracks_b, _ = self._associate(
            candidates_for_low, dets_low, self.match_thresh_low
        )

        for track_idx, det_idx in matched_b:
            candidates_for_low[track_idx].update(dets_low[det_idx])

        # Все треки из первого и второго этапов, которые не нашли совпадения, переходят в LOST
        unmatched_tracks_final = [candidates_for_low[i] for i in unmatched_tracks_b]
        for t in unmatched_tracks_final:
            t.mark_lost()

        # 5. Обработка новых детекций: оставшиеся high-conf детекции порождают новые треки
        new_tracks: List[STrack] = []
        for det_idx in unmatched_dets_high:
            d = dets_high[det_idx]
            strack = STrack(d, self._get_next_id())
            new_tracks.append(strack)

        # 6. Реорганизация списков треков
        new_tracked: List[STrack] = []
        new_unconfirmed: List[STrack] = []
        new_lost: List[STrack] = []

        # Обновляем активные треки
        for t in all_active_tracks:
            if t.state == TrackState.TRACKED:
                new_tracked.append(t)
            elif t.state == TrackState.NEW:
                if t.hits >= self.min_hits_to_confirm:
                    t.state = TrackState.TRACKED
                    t.is_confirmed = True
                    new_tracked.append(t)
                elif t.time_since_update == 0:
                    new_unconfirmed.append(t)
            elif t.state == TrackState.LOST:
                if t.time_since_update <= self.max_lost_frames:
                    new_lost.append(t)
                else:
                    t.mark_removed()

        # Добавляем новые треки
        for t in new_tracks:
            if t.hits >= self.min_hits_to_confirm:
                t.state = TrackState.TRACKED
                t.is_confirmed = True
                new_tracked.append(t)
            else:
                new_unconfirmed.append(t)

        # Сохраняем состояние
        self.tracked_stracks = new_tracked
        self.unconfirmed_stracks = new_unconfirmed
        self.lost_stracks = new_lost

        # Формируем результат для возврата (только активные подтвержденные треки)
        output_objects: List[TrackedObject] = []
        for t in self.tracked_stracks:
            if t.is_confirmed and t.time_since_update == 0:
                output_objects.append(t.to_tracked_object())

        return output_objects

    @staticmethod
    def _associate(
        tracks: List[STrack],
        detections: List[Detection],
        iou_distance_thresh: float,
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Жадное сопоставление треков и детекций по максимальному IoU (1 - distance).
        """
        if not tracks or not detections:
            return [], list(range(len(tracks))), list(range(len(detections)))

        cost_matrix = np.zeros((len(tracks), len(detections)), dtype=np.float32)
        for t_idx, track in enumerate(tracks):
            track_box = BoundingBox(*track.kalman.get_state())
            for d_idx, det in enumerate(detections):
                iou = track_box.iou(det.bbox)
                # Если классы не совпадают, штрафуем совпадение
                if track.class_id != det.class_id:
                    iou *= 0.5
                cost_matrix[t_idx, d_idx] = 1.0 - iou

        matched_tracks: List[int] = []
        matched_dets: List[int] = []
        matches: List[Tuple[int, int]] = []

        # Жадное сопоставление минимальной дистанции (максимального IoU)
        flat_indices = np.argsort(cost_matrix, axis=None)
        rows, cols = np.unravel_index(flat_indices, cost_matrix.shape)

        for r, c in zip(rows, cols):
            if r in matched_tracks or c in matched_dets:
                continue
            if cost_matrix[r, c] > (1.0 - iou_distance_thresh):
                continue
            matched_tracks.append(int(r))
            matched_dets.append(int(c))
            matches.append((int(r), int(c)))

        unmatched_tracks = [i for i in range(len(tracks)) if i not in matched_tracks]
        unmatched_dets = [j for j in range(len(detections)) if j not in matched_dets]

        return matches, unmatched_tracks, unmatched_dets

    def reset(self) -> None:
        """Сброс всех активных треков."""
        self.tracked_stracks.clear()
        self.lost_stracks.clear()
        self.unconfirmed_stracks.clear()
        self.frame_id = 0
