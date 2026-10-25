"""
Tests for violation screenshot preservation:
- CameraHub violation frame storage
- /snapshot.jpg endpoint
- Ongoing violation snapshot update in CVPipeline
- EventStore cleanup of superseded snapshots
"""
import os
import shutil
import tempfile
import time
import unittest
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.camera_hub import camera_hub
from app.store import EventStore
from engine.deduplication.types import ConfirmedIncident, IncidentState
from engine.inference.base import Detection
from engine.pipeline import CVPipeline
from engine.rules.base import BoundingBox, FrameContext, RuleViolation, ViolationSeverity


class TestViolationSnapshot(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_camera_hub_preserves_last_violation_frame(self):
        """Проверяет, что CameraHub сохраняет кадр нарушения даже после поступления кадров без нарушения."""
        cam_id = "test-cam-violation"
        # 1. Помещаем кадр нарушения (красный)
        violation_frame = np.zeros((200, 200, 3), dtype=np.uint8)
        violation_frame[:, :] = (0, 0, 255)
        camera_hub.set_violation_frame(cam_id, violation_frame)

        # 2. Помещаем последующие обычные кадры (зеленые)
        normal_frame = np.zeros((200, 200, 3), dtype=np.uint8)
        normal_frame[:, :] = (0, 255, 0)
        camera_hub.set_frame(cam_id, normal_frame)

        # 3. get_violation_frame возвращает именно кадр нарушения
        v_bytes = camera_hub.get_violation_frame(cam_id)
        self.assertIsNotNone(v_bytes)

        # 4. get_snapshot отдает приоритет нарушению
        snap_bytes = camera_hub.get_snapshot(cam_id)
        self.assertEqual(snap_bytes, v_bytes)

    def test_camera_snapshot_api_endpoint(self):
        """Проверяет эндпоинты /snapshot.jpg и /frame.jpg?mode=snapshot."""
        cam_id = "test-cam-endpoint"
        v_frame = np.full((100, 100, 3), 200, dtype=np.uint8)
        camera_hub.set_violation_frame(cam_id, v_frame)

        # Проверка /snapshot.jpg
        res = self.client.get(f"/api/v1/cameras/{cam_id}/snapshot.jpg")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "image/jpeg")
        self.assertGreater(len(res.content), 50)

        # Проверка /frame.jpg?mode=snapshot
        res_mode = self.client.get(f"/api/v1/cameras/{cam_id}/frame.jpg?mode=snapshot")
        self.assertEqual(res_mode.status_code, 200)
        self.assertEqual(res_mode.content, res.content)

    def test_pipeline_updates_snapshot_for_active_violations(self):
        """Проверяет, что CVPipeline обновляет стоп-кадр для длящегося активного нарушения."""
        from app.storage.local import LocalStorageProvider
        from engine.inference.factory import create_inference_engine

        mock_engine = create_inference_engine(backend="MOCK")
        storage = LocalStorageProvider(base_dir=self.temp_dir)
        pipeline = CVPipeline(
            inference_engine=mock_engine,
            storage_provider=storage,
            camera_id="cam-pipeline-test",
        )

        # Создаем активный инцидент
        inc = ConfirmedIncident(
            rule_name="danger_zone",
            rule_id="DZ-01",
            severity=ViolationSeverity.HIGH,
            camera_id="cam-pipeline-test",
            track_id=1,
            involved_track_ids=[1],
            description="Тестовое нарушение",
            bbox=BoundingBox(10, 10, 50, 50),
            first_seen_at=time.time(),
            confirmed_at=time.time(),
            last_seen_at=time.time(),
            duration_seconds=1.0,
            state=IncidentState.ACTIVE,
        )

        # Инициализируем снапшот
        frame1 = np.full((100, 100, 3), 50, dtype=np.uint8)
        initial_url = storage.save_snapshot(frame1, inc.incident_id, "cam-pipeline-test")
        inc.snapshot_path = initial_url

        # Мокируем антиспам, возвращающий активный инцидент
        pipeline.anti_spam.process = lambda violations, ctx: ([], [inc])

        # Сырое нарушение для трека 1
        raw_violation = RuleViolation(
            rule_name="danger_zone",
            rule_id="DZ-01",
            severity=ViolationSeverity.HIGH,
            camera_id="cam-pipeline-test",
            track_id=1,
            description="Тестовое нарушение в процессе",
            bbox=BoundingBox(20, 20, 60, 60),
            timestamp=time.time(),
        )
        pipeline.rules_engine.evaluate = lambda tracks, ctx: [raw_violation]

        # Обрабатываем новый кадр
        frame2 = np.full((100, 100, 3), 220, dtype=np.uint8)
        res = pipeline.process_frame(frame2, detections=[])

        # Снапшот должен остаться сохраненным и валидным
        self.assertTrue(inc.snapshot_path.startswith("/static/snapshots/"))

    def test_event_store_removes_superseded_snapshots_on_merge(self):
        """Проверяет, что при объединении событий в EventStore удаляется старый скриншот."""
        import app.config as cfg
        snap_dir = os.path.join(self.temp_dir, "standalone_snaps")
        os.makedirs(snap_dir, exist_ok=True)
        old_snap_dir = cfg.SNAP_DIR
        cfg.SNAP_DIR = snap_dir
        try:
            db_path = os.path.join(self.temp_dir, "events.db")
            store = EventStore(path=db_path)

            now = time.time()
            snap1 = "snap_old_1.jpg"
            snap2 = "snap_new_2.jpg"
            with open(os.path.join(snap_dir, snap1), "wb") as f:
                f.write(b"old image bytes")
            with open(os.path.join(snap_dir, snap2), "wb") as f:
                f.write(b"new image bytes")

            # Первое событие
            ev1 = {
                "ts": now,
                "camera": "cam1",
                "type": "no_helmet",
                "label": "Без каски",
                "severity": "warning",
                "zone": "Цех № 1",
                "track_id": 1,
                "status": "new",
                "snapshot": snap1,
                "latency_ms": 10.0,
            }
            store.add(ev1)

            # Второе объединенное событие в пределах окна слияния
            ev2 = {
                "ts": now + 5.0,
                "camera": "cam1",
                "type": "no_helmet",
                "label": "Без каски",
                "severity": "critical",
                "zone": "Цех № 1",
                "track_id": 1,
                "status": "new",
                "snapshot": snap2,
                "latency_ms": 12.0,
            }
            store.add(ev2)

            # Старый файл должен быть удален, новый — остаться
            self.assertFalse(os.path.exists(os.path.join(snap_dir, snap1)))
            self.assertTrue(os.path.exists(os.path.join(snap_dir, snap2)))
        finally:
            cfg.SNAP_DIR = old_snap_dir
