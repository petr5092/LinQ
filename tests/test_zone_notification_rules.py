import pytest
from app.services.notifications.store import NotificationStore
from app.services.notifications.manager import NotificationManager
from fastapi.testclient import TestClient
from app.main import app


def test_zone_notification_store(tmp_path):
    db_file = str(tmp_path / "test_notifications.db")
    store = NotificationStore(db_path=db_file)

    # По умолчанию правило включено
    assert store.is_notification_enabled_for_zone("Цех № 1", "Падение человека") is True

    # Отключаем
    store.set_zone_rule("Цех № 1", "Падение человека", False)
    assert store.is_notification_enabled_for_zone("Цех № 1", "Падение человека") is False

    # Включаем обратно
    store.set_zone_rule("Цех № 1", "Падение человека", True)
    assert store.is_notification_enabled_for_zone("Цех № 1", "Падение человека") is True

    # Проверяем получение матрицы
    store.set_zone_rule("Цех № 1", "Контроль касок и респираторов", False)
    data = store.get_zone_rules()
    assert "Цех № 1Контроль касок и респираторов" in data["rules"]
    assert data["rules"]["Цех № 1Контроль касок и респираторов"] is False


def test_manager_filtering_by_zone_rules(tmp_path):
    mgr = NotificationManager()
    mgr.store = NotificationStore(db_path=str(tmp_path / "test_notifications.db"))

    # Инцидент без каски в Цехе № 1
    incident_ppe = {
        "camera_id": "CAM-01",
        "zone": "Цех № 1",
        "title": "Сотрудник без каски",
        "rule_name": "ppe_compliance",
        "description": "Сотрудник без каски в рабочей зоне",
        "id": "INC-01",
    }

    # По умолчанию разрешено
    assert mgr.is_incident_notification_allowed(incident_ppe) is True

    # Выключаем контроль касок в Цехе № 1
    mgr.store.set_zone_rule("Цех № 1", "Контроль касок и респираторов", False)
    assert mgr.is_incident_notification_allowed(incident_ppe) is False

    # В другом цехе — разрешено
    incident_other_zone = dict(incident_ppe, zone="Склад", id="INC-02")
    assert mgr.is_incident_notification_allowed(incident_other_zone) is True

    # Другое правило в том же Цехе № 1 (Падение) — разрешено
    incident_fall = {
        "camera_id": "CAM-01",
        "zone": "Цех № 1",
        "title": "Падение человека",
        "rule_name": "fall_detection",
        "id": "INC-03",
    }
    assert mgr.is_incident_notification_allowed(incident_fall) is True

    # Тепловизор: перегрев оборудования в Цехе № 1
    incident_thermal = {
        "camera_id": "THERMAL-01",
        "zone": "Цех № 1",
        "title": "Перегрев: motor_bearing",
        "type": "environment",
        "description": "Температура 92.5°C превысила порог 85.0°C",
        "id": "INC-04",
    }
    assert mgr.is_incident_notification_allowed(incident_thermal) is True

    # Отключаем температурный контроль для Цеха № 1
    mgr.store.set_zone_rule("Цех № 1", "Температурный контроль и перегрев", False)
    assert mgr.is_incident_notification_allowed(incident_thermal) is False


def test_api_notification_rules():
    client = TestClient(app)

    # Установка правила
    resp = client.post(
        "/api/v1/notifications/rules",
        json={"zone": "Цех № 1", "rule": "Падение человека", "enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # Получение правил
    resp = client.get("/api/v1/notifications/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert "Цех № 1Падение человека" in data["rules"]
    assert data["rules"]["Цех № 1Падение человека"] is False

    # Возврат в исходное состояние
    client.post(
        "/api/v1/notifications/rules",
        json={"zone": "Цех № 1", "rule": "Падение человека", "enabled": True},
    )
