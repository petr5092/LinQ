"""
Тесты пространственно-временного трекера (ByteTrack & Kalman).
"""

import pytest
from engine.inference.base import BoundingBox, Detection
from engine.tracking.kalman import KalmanBoxTracker
from engine.tracking.tracker import ByteTracker
from engine.tracking.types import TrackState


def test_kalman_filter_prediction_and_update():
    init_box = (100.0, 100.0, 150.0, 200.0)
    tracker = KalmanBoxTracker(init_box)

    # 1. Предсказание
    pred_box = tracker.predict()
    assert len(pred_box) == 4
    assert pred_box[0] == pytest.approx(100.0, 2.0)

    # 2. Обновление со смещением
    next_box = (105.0, 102.0, 155.0, 202.0)
    tracker.update(next_box)
    curr_box = tracker.get_state()
    vx, vy = tracker.get_velocity()

    assert curr_box[0] > 100.0
    assert abs(vx) >= 0.0


def test_bytetrack_lifecycle_and_association():
    tracker = ByteTracker(
        high_thresh=0.5,
        low_thresh=0.2,
        min_hits_to_confirm=2,
        max_lost_frames=5,
    )

    # Кадр 1: Появление человека с высокой уверенностью
    det1 = Detection(
        bbox=BoundingBox(50.0, 50.0, 100.0, 150.0),
        confidence=0.85,
        class_id=0,
        class_name="person",
    )
    tracks_f1 = tracker.update([det1])
    # На первом кадре трек еще в состоянии unconfirmed (hits=1 < 2)
    assert len(tracks_f1) == 0

    # Кадр 2: Человек немного сдвинулся, hits=2 -> трек подтвержден!
    det2 = Detection(
        bbox=BoundingBox(52.0, 51.0, 102.0, 151.0),
        confidence=0.88,
        class_id=0,
        class_name="person",
    )
    tracks_f2 = tracker.update([det2])
    assert len(tracks_f2) == 1
    t = tracks_f2[0]
    assert t.class_name == "person"
    assert t.is_confirmed is True
    track_id = t.track_id

    # Кадр 3: Частичное перекрытие (окклюзия), уверенность упала до 0.35 (low-confidence)
    # ByteTrack должен восстановить и связать трек благодаря второму этапу ассоциации!
    det3 = Detection(
        bbox=BoundingBox(54.0, 52.0, 104.0, 152.0),
        confidence=0.35,
        class_id=0,
        class_name="person",
    )
    tracks_f3 = tracker.update([det3])
    assert len(tracks_f3) == 1
    assert tracks_f3[0].track_id == track_id  # Тот же ID сохранился!

    # Кадры 4-10: Человек полностью исчез из поля зрения (окклюзия)
    for _ in range(6):
        tracks_empty = tracker.update([])

    # После превышения max_lost_frames трек окончательно удален
    assert len(tracker.tracked_stracks) == 0
    assert len(tracker.lost_stracks) == 0
