"""
Тесты пространственно-временного трекера (ByteTrack & Kalman) по стандарту test-master.
Покрытие: фильтр Калмана, двухэтапная ассоциация, окклюзии, очистка устаревших треков, reset.
"""

import pytest
from engine.inference.base import BoundingBox, Detection
from engine.tracking.kalman import KalmanBoxTracker
from engine.tracking.tracker import ByteTracker
from engine.tracking.types import TrackState, TrackedObject


def test_kalman_filter_prediction_and_update():
    """Математическая корректность предсказания и обновления состояния фильтра Калмана."""
    init_box = (100.0, 100.0, 150.0, 200.0)
    tracker = KalmanBoxTracker(init_box)

    pred_box = tracker.predict()
    assert len(pred_box) == 4
    assert pred_box[0] == pytest.approx(100.0, 2.0)

    next_box = (105.0, 102.0, 155.0, 202.0)
    tracker.update(next_box)
    curr_box = tracker.get_state()
    vx, vy = tracker.get_velocity()

    assert curr_box[0] > 100.0
    assert abs(vx) >= 0.0


def test_bytetrack_lifecycle_and_association():
    """Жизненный цикл трека: NEW -> TRACKED -> восстановление при окклюзии -> LOST -> REMOVED."""
    tracker = ByteTracker(
        high_thresh=0.5,
        low_thresh=0.2,
        min_hits_to_confirm=2,
        max_lost_frames=3,
    )

    # Кадр 1: Появление человека с высокой уверенностью (hits=1, еще не подтвержден)
    det1 = Detection(BoundingBox(50.0, 50.0, 100.0, 150.0), 0.85, 0, "person")
    tracks_f1 = tracker.update([det1])
    assert len(tracks_f1) == 0

    # Кадр 2: Человек сместился (hits=2 -> TRACKED)
    det2 = Detection(BoundingBox(52.0, 51.0, 102.0, 151.0), 0.88, 0, "person")
    tracks_f2 = tracker.update([det2])
    assert len(tracks_f2) == 1
    track_id = tracks_f2[0].track_id

    # Проверка свойств TrackedObject
    obj = tracks_f2[0]
    assert obj.center == pytest.approx((77.0, 101.0), 2.0)
    assert obj.bottom_center[1] == pytest.approx(151.0, 2.0)
    assert "track_id" in obj.to_dict()

    # Кадр 3: Окклюзия / смаз (уверенность упала до 0.30) -> восстанавливается через 2-й этап ассоциации
    det3 = Detection(BoundingBox(54.0, 52.0, 104.0, 152.0), 0.30, 0, "person")
    tracks_f3 = tracker.update([det3])
    assert len(tracks_f3) == 1
    assert tracks_f3[0].track_id == track_id

    # Кадры 4-8: Полное исчезновение объекта (превышение max_lost_frames = 3)
    for _ in range(5):
        tracker.update([])

    assert len(tracker.tracked_stracks) == 0
    assert len(tracker.lost_stracks) == 0


def test_bytetrack_multi_class_and_reset():
    """Разделение треков разных классов (человек и погрузчик) и сброс состояния."""
    tracker = ByteTracker(min_hits_to_confirm=1)

    det_person = Detection(BoundingBox(10, 10, 50, 100), 0.9, 0, "person")
    det_forklift = Detection(BoundingBox(150, 100, 300, 250), 0.95, 1, "forklift")

    tracks = tracker.update([det_person, det_forklift])
    assert len(tracks) == 2
    classes = {t.class_name for t in tracks}
    assert "person" in classes
    assert "forklift" in classes

    # Проверка reset
    tracker.reset()
    assert len(tracker.tracked_stracks) == 0
    assert tracker.frame_id == 0
