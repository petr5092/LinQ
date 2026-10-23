"""
Интеграционные сквозные тесты CV Pipeline LinQ Safety Guard.
"""

import os
import shutil
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


@pytest.fixture
def temp_storage_dir(tmp_path):
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir()
    yield str(storage_dir)
    shutil.rmtree(str(storage_dir), ignore_errors=True)


def test_cv_pipeline_end_to_end(temp_storage_dir):
    # 1. Настройка опасной зоны
    zone = ZoneDefinition(
        zone_id="test_dz",
        name="Испытательный полигон",
        polygon=[(100.0, 100.0), (400.0, 100.0), (400.0, 400.0), (100.0, 400.0)],
        forbidden_classes=["person"],
    )
    rules_engine = RulesEngine()
    rules_engine.add_rule(DangerZoneRule(zones=[zone]))

    # 2. Мок-детекция рабочего, находящегося внутри опасной зоны (стопы на 250, 350)
    violating_det = Detection(
        bbox=BoundingBox(230.0, 200.0, 270.0, 350.0),
        confidence=0.92,
        class_id=0,
        class_name="person",
    )
    inference_engine = MockInferenceEngine(
        canned_detections=[[violating_det]],
        simulated_delay_ms=2.0,
    )

    # 3. Настройка хранилища и анти-спама
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

    # Проверка метрик
    last_res = results[-1]
    assert last_res.metrics.frames_processed == 5
    assert last_res.metrics.fps > 0.0
    assert last_res.metrics.inference_time_ms > 0.0
    assert last_res.metrics.tracking_time_ms >= 0.0

    # Проверка выявления инцидента
    assert pipeline.incidents_total == 1
    assert len(received_incidents) == 1

    inc = received_incidents[0]
    assert inc.rule_name == "danger_zone"
    assert inc.zone_id == "test_dz"
    assert inc.snapshot_path is not None

    # Проверка формирования URL снапшота и физического сохранения на диск
    assert inc.snapshot_path.startswith("/static/snapshots")
    rel_path = inc.snapshot_path.replace("/static/snapshots", "").lstrip("/\\")
    disk_file = os.path.join(temp_storage_dir, rel_path)
    assert os.path.exists(disk_file)
    assert os.path.getsize(disk_file) > 0
