import pytest
from app.services.notifications.store import NotificationStore
from app.services.notifications.telegram import TelegramClient


def test_telegram_caption_formatting_thermal(tmp_path):
    store = NotificationStore(db_path=str(tmp_path / "test.db"))
    client = TelegramClient(token="mock:token", store=store)

    # 1. Thermal event with description containing temperatures
    event_thermal = {
        "id": "TH-001",
        "camera_id": "THERMAL-OSF-TEST",
        "camera_name": "Тепловизор · тест OSF",
        "zone": "Сборочный цех",
        "title": "Перегрев: Сборочный цех (+2.4 °C)",
        "severity": "critical",
        "type": "environment",
        "description": "В зоне «Сборочный цех» зафиксирован перегрев: 23.4 °C при пороге 21.0 °C (превышение: +2.4 °C).",
        "action": "Проверьте систему охлаждения узла.",
        "time": "14:32:10",
        "status": "new",
    }

    caption = client.format_caption(event_thermal)
    assert "🔥" in caption
    assert "Перегрев: Сборочный цех (+2.4 °C)" in caption
    assert "Камера: <b>Тепловизор · тест OSF</b>" in caption
    assert "Температура: <b>23.4 °C</b> (порог: <b>21.0 °C</b>)" in caption
    assert "Превышение порога: +2.4 °C" in caption
    assert "Действие: Проверьте систему охлаждения узла." in caption
    assert "14:32:10" in caption
    assert "Открыть в дашборде" not in caption


def test_telegram_caption_calculates_excess_from_numbers(tmp_path):
    store = NotificationStore(db_path=str(tmp_path / "test.db"))
    client = TelegramClient(token="mock:token", store=store)

    # 2. Event with raw temperature and threshold without explicit diff
    event_calc = {
        "id": "TH-002",
        "camera_id": "THERMAL-01",
        "zone": "Цех № 1",
        "title": "Перегрев: motor_bearing",
        "severity": "high",
        "type": "environment",
        "description": "В зоне «motor_bearing» температура достигла 92.5 °C при пороге 85.0 °C.",
        "time": "15:00:00",
        "status": "new",
    }

    caption = client.format_caption(event_calc)
    assert "🔥" in caption
    assert "Температура: <b>92.5 °C</b> (порог: <b>85.0 °C</b>)" in caption
    assert "Превышение порога: +7.5 °C" in caption


def test_telegram_caption_formatting_non_thermal(tmp_path):
    store = NotificationStore(db_path=str(tmp_path / "test.db"))
    client = TelegramClient(token="mock:token", store=store)

    event_ppe = {
        "id": "INC-101",
        "camera_id": "CAM-01",
        "zone": "Цех № 1",
        "title": "Сотрудник без каски",
        "severity": "warning",
        "type": "person",
        "description": "У сотрудника #3 отсутствует защитная каска",
        "action": "Оповестите мастера участка.",
        "time": "12:00:00",
        "status": "new",
    }

    caption = client.format_caption(event_ppe)
    assert "🔶" in caption or "🟡" in caption
    assert "Сотрудник без каски" in caption
    assert "Камера: <b>CAM-01</b>" in caption
    assert "Превышение порога" not in caption
