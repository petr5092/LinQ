import os
import sys
import unittest
from pathlib import Path

# Добавляем корень проекта в sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from starlette.testclient import TestClient
from app.main import app


class TestLinQApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        self.assertGreaterEqual(len(sites), 3)
        site_ids = [s["id"] for s in sites]
        self.assertIn("north", site_ids)
        self.assertIn("south", site_ids)
        self.assertIn("east", site_ids)

        # Проверка вложенности цехов и зон
        north_site = next(s for s in sites if s["id"] == "north")
        self.assertGreater(len(north_site["workshops"]), 0)
        first_workshop = north_site["workshops"][0]
        self.assertGreater(len(first_workshop["zones"]), 0)

    def test_04_cameras_crud(self):
        """Тестирование CRUD для видеокамер"""
        # 1. Получение списка
        res_list = self.client.get("/api/v1/cameras")
        self.assertEqual(res_list.status_code, 200)
        cameras = res_list.json()
        self.assertGreaterEqual(len(cameras), 1)

        # 2. Создание тестовой камеры
        test_cam = {
            "id": "CAM-TEST-99",
            "name": "Тестовая камера для проверки",
            "zone": "Цех № 1",
            "workshop": "Корпус А",
            "site_id": "north",
            "online": True,
            "fps": 30.0,
        }
        res_create = self.client.post("/api/v1/cameras", json=test_cam)
        self.assertEqual(res_create.status_code, 201)
        created_data = res_create.json()
        self.assertEqual(created_data["id"], "CAM-TEST-99")

        # 3. Получение созданной камеры
        res_get = self.client.get("/api/v1/cameras/CAM-TEST-99")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["name"], "Тестовая камера для проверки")

        # 4. Обновление (PATCH)
        res_patch = self.client.patch("/api/v1/cameras/CAM-TEST-99", json={"online": False, "fps": 15.0})
        self.assertEqual(res_patch.status_code, 200)
        self.assertFalse(res_patch.json()["online"])
        self.assertEqual(res_patch.json()["fps"], 15.0)

        # 5. Удаление (DELETE)
        res_del = self.client.delete("/api/v1/cameras/CAM-TEST-99")
        self.assertEqual(res_del.status_code, 200)

        # 6. Проверка удаления
        res_check = self.client.get("/api/v1/cameras/CAM-TEST-99")
        self.assertEqual(res_check.status_code, 404)

    def test_05_incidents_flow(self):
        """Тестирование создания и жизненного цикла инцидента"""
        # 1. Список инцидентов
        res_list = self.client.get("/api/v1/incidents?page=1&size=10")
        self.assertEqual(res_list.status_code, 200)
        page_data = res_list.json()
        self.assertIn("items", page_data)
        self.assertGreaterEqual(page_data["total"], 1)

        # 2. Регистрация нового инцидента
        new_incident = {
            "id": "TK-TEST-01",
            "site_id": "north",
            "camera_id": "CAM-01",
            "zone": "Цех № 1",
            "title": "Тестовое нарушение СИЗ",
            "time": "15:00:00",
            "severity": "critical",
            "type": "person",
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
        self.assertEqual(created["id"], "TK-TEST-01")
        self.assertEqual(created["employee"]["name"], "Тестовый Рабочий")
        self.assertEqual(created["contact"]["name"], "Тестовый Мастер")

        # 3. Перевод в работу: new -> working
        res_work = self.client.patch("/api/v1/incidents/TK-TEST-01/status", json={"status": "working"})
        self.assertEqual(res_work.status_code, 200)
        self.assertEqual(res_work.json()["status"], "working")

        # 4. Закрытие инцидента: working -> resolved
        res_resolve = self.client.patch("/api/v1/incidents/TK-TEST-01/status", json={"status": "resolved"})
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
        self.assertGreater(data["incidents"]["total"], 0)
        self.assertGreater(data["cameras"]["total"], 0)

    def test_07_websocket_connection(self):
        """Проверка WebSocket соединения /ws/events"""
        with self.client.websocket_connect("/ws/events") as websocket:
            data = websocket.receive_json()
            self.assertEqual(data["event"], "CONNECTED")
            websocket.send_text("ping")
            response = websocket.receive_text()
            self.assertEqual(response, "pong")


if __name__ == "__main__":
    unittest.main()
