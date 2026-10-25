import os
import sys
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch

# Добавляем корень проекта в sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from starlette.testclient import TestClient
from app.main import app
from app.services.camera_hub import camera_hub
from app.db.session import SessionLocal
from app.db.models.incident import Incident
from app.services.notifications import notification_manager
import numpy as np


class TestLinQApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.seed import seed_database
        seed_database()
        cls.client = TestClient(app)

    def test_01_root_endpoint(self):
        """Проверка корневого эндпоинта /"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("docs_url", data)

    def test_02_healthcheck(self):
        """Проверка эндпоинта /health и /api/v1/health"""
        for url in ["/health", "/api/v1/health"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
            self.assertTrue(data["database"], "База данных должна быть доступна")
            self.assertTrue(data["storage"]["healthy"], "Хранилище должно быть доступно")

    def test_03_sites_list(self):
        """Проверка списка промышленных площадок"""
        response = self.client.get("/api/v1/sites")
        self.assertEqual(response.status_code, 200)
        sites = response.json()
        self.assertGreaterEqual(len(sites), 1)
        site_ids = [s["id"] for s in sites]
        self.assertIn("north", site_ids)

    def test_04_cameras_list_and_filter(self):
        """Проверка получения списка камер и фильтрации"""
        # Все камеры
        res_all = self.client.get("/api/v1/cameras")
        self.assertEqual(res_all.status_code, 200)
        cams = res_all.json()
        self.assertGreaterEqual(len(cams), 1)

        # Фильтр по онлайн статусу
        res_online = self.client.get("/api/v1/cameras?online=true")
        self.assertEqual(res_online.status_code, 200)
        for cam in res_online.json():
            self.assertTrue(cam["online"])

    def test_05_incidents_lifecycle(self):
        """Проверка жизненного цикла инцидента: создание -> чтение -> смена статуса"""
        # 1. Получение списка инцидентов
        res_list = self.client.get("/api/v1/incidents")
        self.assertEqual(res_list.status_code, 200)
        data = res_list.json()
        self.assertIn("items", data)
        self.assertIsInstance(data["total"], int)

        # 2. Создание нового инцидента
        inc_id = f"test-inc-{uuid.uuid4().hex[:8]}"
        new_incident = {
            "id": inc_id,
            "type": "no_helmet",
            "title": "Отсутствие защитной каски",
            "severity": "critical",
            "camera_id": "CAM-01",
            "site_id": "north",
            "zone": "gate",
            "time": "15:30:00",
            "description": "Тестовая проверка жизненного цикла инцидента.",
            "action": "Проверить статус реагирования.",
            "status": "new",
            "box": [50.0, 50.0, 20.0, 40.0],
            "employee_name": "Тестовый Рабочий",
            "employee_role": "Слесарь",
            "contact_name": "Тестовый Мастер",
            "contact_phone": "+7 999 000-00-00",
        }
        res_create = self.client.post("/api/v1/incidents", json=new_incident)
        self.assertEqual(res_create.status_code, 201)
        created = res_create.json()
        self.assertEqual(created["id"], inc_id)
        self.assertEqual(created["employee"]["name"], "Тестовый Рабочий")
        self.assertEqual(created["contact"]["name"], "Тестовый Мастер")

        # 3. Перевод в работу: new -> working
        res_work = self.client.patch(f"/api/v1/incidents/{inc_id}/status", json={"status": "working"})
        self.assertEqual(res_work.status_code, 200)
        self.assertEqual(res_work.json()["status"], "working")

        # 4. Закрытие инцидента: working -> resolved
        res_resolve = self.client.patch(f"/api/v1/incidents/{inc_id}/status", json={"status": "resolved"})
        self.assertEqual(res_resolve.status_code, 200)
        self.assertEqual(res_resolve.json()["status"], "resolved")

    def test_06_analytics_summary(self):
        """Проверка аналитической сводки дашборда"""
        response = self.client.get("/api/v1/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("incidents", data)
        self.assertIn("severity", data)
        self.assertIn("cameras", data)
        self.assertIn("today", data)
        self.assertEqual(len(data["today"]["hourly"]), 24)
        self.assertEqual(
            data["incidents"]["total"],
            data["incidents"]["new"]
            + data["incidents"]["working"]
            + data["incidents"]["resolved"]
            + data["incidents"]["dismissed"],
        )

    def test_07_websocket_connection(self):
        """Проверка WebSocket соединения /ws/events"""
        with self.client.websocket_connect("/ws/events") as websocket:
            data = websocket.receive_json()
            self.assertEqual(data["event"], "CONNECTED")
            websocket.send_text("ping")
            response = websocket.receive_text()
            self.assertEqual(response, "pong")

    def test_08_notifications_endpoints(self):
        """Проверка эндпоинтов управления уведомлениями"""
        from unittest.mock import patch
        from app.services.notifications import notification_manager

        with patch.object(notification_manager, "_send_with_retry", return_value=True):
            res_status = self.client.get("/api/v1/notifications/status")
            self.assertEqual(res_status.status_code, 200)
            data = res_status.json()
            self.assertIn("telegram", data)
            self.assertIn("subscribers", data)
            self.assertIn("deliveries", data)

            res_test = self.client.post("/api/v1/notifications/test", json={})
            self.assertEqual(res_test.status_code, 200)
            self.assertTrue(res_test.json()["ok"])

            # Проверка синхронизации алертов и журнала
            res_sync = self.client.post("/api/v1/notifications/sync")
            self.assertEqual(res_sync.status_code, 200)
            self.assertTrue(res_sync.json()["ok"])
            self.assertIn("synced_count", res_sync.json())

            # Проверка журнала доставок
            res_delivs = self.client.get("/api/v1/notifications/deliveries")
            self.assertEqual(res_delivs.status_code, 200)
            self.assertIsInstance(res_delivs.json(), list)

    def test_09_camera_live_statuses_and_frame(self):
        """Проверка получения оперативного статуса и стоп-кадра камеры"""
        # Помещаем тестовый кадр в CameraHub
        dummy_frame = np.full((360, 640, 3), 100, dtype=np.uint8)
        camera_hub.set_frame("cam-test-live", dummy_frame)
        camera_hub.update_metrics("cam-test-live", fps=24.5, detect_time_ms=12.3, latency_ms=15.1)

        res_statuses = self.client.get("/api/v1/cameras/statuses/live")
        self.assertEqual(res_statuses.status_code, 200)
        statuses = res_statuses.json()
        self.assertTrue(any(s["camera_id"] == "cam-test-live" for s in statuses))

        res_frame = self.client.get("/api/v1/cameras/cam-test-live/frame.jpg")
        self.assertEqual(res_frame.status_code, 200)
        self.assertEqual(res_frame.headers["content-type"], "image/jpeg")
        self.assertGreater(len(res_frame.content), 100)

        res_metrics = self.client.get("/api/v1/cameras/cam-test-live/metrics")
        self.assertEqual(res_metrics.status_code, 200)
        self.assertEqual(res_metrics.json()["fps"], 24.5)

    def test_10_incidents_export_csv(self):
        """Проверка экспорта журнала инцидентов в CSV"""
        response = self.client.get("/api/v1/incidents/export/csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        text = response.content.decode("utf-8")
        self.assertIn("ID,Время,Камера,Площадка", text)

    def test_11_repeated_incidents_are_merged_by_camera_and_title(self):
        """Repeated detections update one open incident; resolved episodes create a new record."""
        title = f"Test repeated event {uuid.uuid4().hex}"
        base = {
            "type": "person",
            "title": title,
            "severity": "warning",
            "camera_id": "CAM-01",
            "site_id": "north",
            "zone": "Цех № 1",
            "time": "15:30:00",
            "description": "Repeated detector output",
            "action": "Review",
            "status": "new",
        }
        with patch.object(notification_manager, "dispatch_incident") as dispatch, patch.object(
            notification_manager, "refresh_incident"
        ) as refresh:
            first = self.client.post(
                "/api/v1/incidents",
                json={**base, "id": f"test-merge-{uuid.uuid4().hex[:8]}"},
            )
            second = self.client.post(
                "/api/v1/incidents",
                json={
                    **base,
                    "id": f"test-merge-{uuid.uuid4().hex[:8]}",
                    "time": "15:30:01",
                    "severity": "critical",
                },
            )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["id"], first.json()["id"])
        self.assertEqual(second.json()["time"], "15:30:01")
        self.assertEqual(second.json()["severity"], "critical")
        dispatch.assert_called_once()
        refresh.assert_called_once()

        with SessionLocal() as db:
            self.assertEqual(
                db.query(Incident).filter(Incident.camera_id == "CAM-01", Incident.title == title).count(),
                1,
            )

        resolved = self.client.patch(
            f"/api/v1/incidents/{first.json()['id']}/status",
            json={"status": "resolved"},
        )
        self.assertEqual(resolved.status_code, 200)

        next_episode = self.client.post(
            "/api/v1/incidents",
            json={**base, "id": f"test-merge-{uuid.uuid4().hex[:8]}"},
        )
        self.assertEqual(next_episode.status_code, 201)
        self.assertNotEqual(next_episode.json()["id"], first.json()["id"])

        with SessionLocal() as db:
            db.query(Incident).filter(Incident.title == title).delete()
            db.commit()


if __name__ == "__main__":
    unittest.main()
