"""
Интеграционные сквозные тесты CV Pipeline LinQ Safety Guard по стандарту test-master.
Покрытие: E2E-пайплайн, обработка видеофайлов, оверлеи, сброс состояния, отказоустойчивость.
"""

import os
import shutil
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pytest

from app.storage.local import LocalStorageProvider
from engine.deduplication.anti_spam import AntiSpamEngine
from engine.inference.base import BoundingBox, Detection
from engine.inference.mock import MockInferenceEngine
from engine.pipeline import CVPipeline
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.engine import RulesEngine
from engine.tracking.tracker import ByteTracker
from engine.tracking.types import TrackedObject


@pytest.fixture
def temp_storage_dir(tmp_path):
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir()
    yield str(storage_dir)
    shutil.rmtree(str(storage_dir), ignore_errors=True)


def test_cv_pipeline_end_to_end(temp_storage_dir):
    """Сквозной пайплайн: детекция -> трекер -> правила -> антиспам -> сохранение снапшота."""
    zone = ZoneDefinition(
        zone_id="test_dz",
        name="Испытательный полигон",
        polygon=[(100.0, 100.0), (400.0, 100.0), (400.0, 400.0), (100.0, 400.0)],
        forbidden_classes=["person"],
    )
    rules_engine = RulesEngine()
    rules_engine.add_rule(DangerZoneRule(zones=[zone]))

    violating_det = Detection(
        bbox=BoundingBox(230.0, 200.0, 270.0, 350.0),
        confidence=0.92,
        class_id=0,
        class_name="person",
    )
    forklift_det = Detection(
        bbox=BoundingBox(500.0, 500.0, 600.0, 600.0),
        confidence=0.90,
        class_id=1,
        class_name="forklift",
    )

    inference_engine = MockInferenceEngine(
        canned_detections=[[violating_det, forklift_det]],
        simulated_delay_ms=1.0,
    )

    storage_provider = LocalStorageProvider(base_dir=temp_storage_dir)
    anti_spam = AntiSpamEngine(debounce_frames=3, cooldown_seconds=60.0)

    received_incidents = []

    def on_incident(incident, frame):
        received_incidents.append(incident)

    pipeline = CVPipeline(
        inference_engine=inference_engine,
        tracker=ByteTracker(min_hits_to_confirm=1),
        rules_engine=rules_engine,
        anti_spam_engine=anti_spam,
        storage_provider=storage_provider,
        incident_callback=on_incident,
        camera_id="cam_test_01",
    )

    dummy_frame = np.full((720, 1280, 3), 128, dtype=np.uint8)

    # Прогоняем 5 кадров
    results = []
    for f in range(1, 6):
        res = pipeline.process_frame(dummy_frame)
        results.append(res)

    last_res = results[-1]
    assert last_res.metrics.frames_processed == 5
    assert last_res.metrics.fps > 0.0
    assert last_res.metrics.inference_time_ms > 0.0
    assert last_res.metrics.tracking_time_ms >= 0.0

    assert pipeline.incidents_total == 1
    assert len(received_incidents) == 1

    inc = received_incidents[0]
    assert inc.rule_name == "danger_zone"
    assert inc.zone_id == "test_dz"
    assert inc.snapshot_path is not None

    # Физическое сохранение на диск
    assert inc.snapshot_path.startswith("/static/snapshots")
    rel_path = inc.snapshot_path.replace("/static/snapshots", "").lstrip("/\\")
    disk_file = os.path.join(temp_storage_dir, rel_path)
    assert os.path.exists(disk_file)
    assert os.path.getsize(disk_file) > 0


def test_cv_pipeline_video_processing(tmp_path):
    """Покадровая обработка видеофайла через генератор process_video_file."""
    video_path = str(tmp_path / "test_synth.avi")

    # Создаем короткий тестовый видеофайл (5 кадров)
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(video_path, fourcc, 25.0, (320, 240))
    for _ in range(5):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    pipeline = CVPipeline(
        inference_engine=MockInferenceEngine(),
        tracker=ByteTracker(),
    )

    processed_count = 0
    for res in pipeline.process_video_file(video_path, max_frames=3, target_fps=100.0):
        processed_count += 1
        assert res.frame_id == processed_count

    assert processed_count == 3

    # 1. Проверка вызова с несуществующим файлом
    with pytest.raises(FileNotFoundError):
        list(pipeline.process_video_file("missing_video.mp4"))

    # 2. Невозможно открыть существующий файл (isOpened == False)
    with patch("cv2.VideoCapture") as mock_cap_cls:
        bad_cap = MagicMock()
        bad_cap.isOpened.return_value = False
        mock_cap_cls.return_value = bad_cap
        with pytest.raises(RuntimeError):
            list(pipeline.process_video_file(video_path))


def test_cv_pipeline_resilience_and_reset(temp_storage_dir):
    """Устойчивость к исключениям в callback и при сохранении снапшота."""
    def broken_callback(incident, frame):
        raise ValueError("Simulated callback failure")

    mock_storage = MagicMock()
    mock_storage.save_snapshot.side_effect = IOError("Simulated disk full")

    pipeline = CVPipeline(
        inference_engine=MockInferenceEngine(
            canned_detections=[[Detection(BoundingBox(10, 10, 50, 50), 0.9, 0, "person")]]
        ),
        tracker=ByteTracker(min_hits_to_confirm=1),
        anti_spam_engine=AntiSpamEngine(debounce_frames=1),
        storage_provider=mock_storage,
        incident_callback=broken_callback,
    )

    # Пайплайн не должен падать даже при сбое callback или хранилища
    dummy = np.zeros((100, 100, 3), dtype=np.uint8)
    pipeline.process_frame(dummy)

    assert pipeline.frames_processed == 1

    # Проверка сброса
    pipeline.reset()
    assert pipeline.frames_processed == 0
    assert pipeline.incidents_total == 0
