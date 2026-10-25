"""
Комплексный тестовый набор для системы оповещений (Notification System) по стандарту test-master.
Покрытие:
- NotificationStore (CRUD подписчиков, журнал доставок, агрегация статистики, краевые условия)
- NetioClient & Сетевой слой (post_json, post_multipart, ApiError, retry_after, сирена)
- TelegramClient (команды, фильтрация по уровню, форматирование HTML, клавиатура, обработка ошибок)
- NotificationManager (очередь доставки, маршрутизация по severity, синхронизация статусов с БД, повторные попытки)
"""

import json
import os
import tempfile
import time
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from app.services.notifications.manager import NotificationManager
from app.services.notifications.netio import ApiError, NetioClient, post_json, post_multipart
from app.services.notifications.store import NotificationStore
from app.services.notifications.telegram import (
    SEV_LEVELS,
    SEV_ORDER,
    STATUS_MAP,
    STATUS_TEXT,
    TelegramClient,
)


# ==============================================================================
# 1. NotificationStore Tests
# ==============================================================================

@pytest.fixture
def temp_store(tmp_path):
    db_file = tmp_path / "test_notify_store.db"
    store = NotificationStore(str(db_file))
    yield store


def test_store_upsert_and_get_subscriber(temp_store):
    """Проверка создания, чтения и обновления подписчика при конфликте."""
    sub = temp_store.upsert_subscriber("telegram", 12345, "Чат Смены 1", "supergroup", "master")
    assert sub["chat_id"] == "12345"
    assert sub["title"] == "Чат Смены 1"
    assert sub["active"] == 1
    assert sub["min_severity"] == "low"

    # Повторный upsert обновляет заголовок и возвращает обновленную запись
    sub_updated = temp_store.upsert_subscriber("telegram", 12345, "Новое имя", "supergroup")
    assert sub_updated["title"] == "Новое имя"

    fetched = temp_store.get_subscriber("telegram", 12345)
    assert fetched["title"] == "Новое имя"

    assert temp_store.get_subscriber("telegram", 99999) is None


def test_store_list_and_filter_subscribers(temp_store):
    """Проверка фильтрации подписчиков по каналу и активности."""
    temp_store.upsert_subscriber("telegram", "101", "Chat 1", "group")
    temp_store.upsert_subscriber("telegram", "102", "Chat 2", "private")
    temp_store.upsert_subscriber("netio", "device_1", "Relay 1", "hardware")

    # Деактивируем один чат
    temp_store.set_subscriber_active("telegram", "102", False)

    all_subs = temp_store.list_subscribers()
    assert len(all_subs) == 3

    tg_active = temp_store.list_subscribers(channel="telegram", active=True)
    assert len(tg_active) == 1
    assert tg_active[0]["chat_id"] == "101"

    tg_inactive = temp_store.list_subscribers(channel="telegram", active=False)
    assert len(tg_inactive) == 1
    assert tg_inactive[0]["chat_id"] == "102"


def test_store_update_and_delete_subscriber(temp_store):
    """Проверка частичного обновления полей и удаления подписчика."""
    sub = temp_store.upsert_subscriber("telegram", "201", "Team A", "group")
    sid = sub["id"]

    # Обновление min_severity и title
    temp_store.update_subscriber(sid, min_severity="critical", title="Team Alpha")
    updated = temp_store.get_subscriber("telegram", "201")
    assert updated["min_severity"] == "critical"
    assert updated["title"] == "Team Alpha"

    # Пустое обновление не должно падать
    temp_store.update_subscriber(sid, unknown_field="ignored")

    # Удаление
    temp_store.delete_subscriber(sid)
    assert temp_store.get_subscriber("telegram", "201") is None


def test_store_deliveries_and_stats(temp_store):
    """Проверка регистрации доставок и агрегации метрик."""
    temp_store.add_delivery("inc_1", "telegram", "101", "msg_1", "photo", ok=True, latency_ms=12.5)
    temp_store.add_delivery("inc_1", "telegram", "102", None, "photo", ok=False, error="403 Forbidden")
    temp_store.add_delivery("inc_2", "telegram", "101", "msg_2", "text", ok=True, latency_ms=10.0)

    deliveries_1 = temp_store.get_deliveries_for_event("inc_1")
    assert len(deliveries_1) == 1
    assert deliveries_1[0]["message_id"] == "msg_1"

    deliveries_tg = temp_store.get_deliveries_for_event("inc_1", channel="telegram")
    assert len(deliveries_tg) == 1

    stats = temp_store.delivery_stats()
    assert "telegram" in stats
    assert stats["telegram"]["ok"] == 2
    assert stats["telegram"]["failed"] == 1
    assert stats["telegram"]["avg_latency_ms"] > 0


# ==============================================================================
# 2. NetIO & Low-Level HTTP/Multipart Tests
# ==============================================================================

def test_api_error_attributes():
    err = ApiError("Rate limit", code=429, retry_after=15)
    assert str(err) == "Rate limit"
    assert err.code == 429
    assert err.retry_after == 15


def test_post_json_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        code, data = post_json("http://example.com/api", {"test": 123})
        assert code == 200
        assert b"ok" in data


def test_post_json_http_error_with_retry_after():
    with patch("urllib.request.urlopen") as mock_urlopen:
        err = urllib.error.HTTPError(
            url="http://example.com",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "10"},
            fp=None,
        )
        mock_urlopen.side_effect = err

        with pytest.raises(ApiError) as exc_info:
            post_json("http://example.com", {})

        assert exc_info.value.code == 429
        assert exc_info.value.retry_after == 10


def test_post_json_network_error():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with pytest.raises(ApiError) as exc_info:
            post_json("http://example.com", {})

        assert "Connection refused" in str(exc_info.value)


def test_post_multipart_success(tmp_path):
    test_file = tmp_path / "snap.jpg"
    test_file.write_bytes(b"\xff\xd8\xfffakejpeg")

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true, "result": {"message_id": 99}}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        code, raw = post_multipart(
            url="https://api.telegram.org/sendPhoto",
            fields={"chat_id": "123", "caption": "Alert"},
            files={"photo": ("snap.jpg", test_file.read_bytes())},
        )
        assert code == 200
        assert b"message_id" in raw


def test_netio_client_trigger():
    client = NetioClient(host="192.168.1.100", port=8080)
    with patch("app.services.notifications.netio.post_json") as mock_post:
        mock_post.return_value = (200, b"{}")
        assert client.trigger_siren(output_id=2, action=1) is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "192.168.1.100:8080/netio.json" in args[0]
        assert args[1]["Outputs"][0]["ID"] == 2

    with patch("app.services.notifications.netio.post_json", side_effect=Exception("Timeout")):
        assert client.trigger_siren() is False


# ==============================================================================
# 3. TelegramClient Logic & Formatting Tests
# ==============================================================================

@pytest.fixture
def mock_telegram_client(temp_store):
    client = TelegramClient(
        token="123456:TEST_TOKEN",
        store=temp_store,
        base_url="https://api.telegram.org",
        public_url="http://dashboard.local",
    )
    return client


def test_telegram_info_and_links(mock_telegram_client):
    mock_telegram_client.username = "safety_guard_bot"
    info = mock_telegram_client.info()
    assert info["configured"] is True
    assert info["username"] == "safety_guard_bot"
    assert "startgroup=linq" in info["links"]["group"]
    assert "startchannel=linq" in info["links"]["channel"]
    assert "start=linq" in info["links"]["private"]


def test_telegram_is_gone_detection(mock_telegram_client):
    assert mock_telegram_client.is_gone(ApiError("Forbidden: bot was blocked by the user", code=403)) is True
    assert mock_telegram_client.is_gone(ApiError("Bad Request: chat not found", code=400)) is True
    assert mock_telegram_client.is_gone(ApiError("Forbidden: bot was kicked from the group chat", code=403)) is True
    assert mock_telegram_client.is_gone(ApiError("Internal server error", code=500)) is False


def test_telegram_caption_formatting(mock_telegram_client):
    event = {
        "rule_label": "Отсутствие защитной каски",
        "severity": "critical",
        "camera_name": "Камера цеха №1",
        "zone_name": "Сборочный сектор",
        "timestamp_str": "14:20:00 24.10.2026",
        "status": "new",
    }
    caption_new = mock_telegram_client.format_caption(event)
    assert "🚨 <b>Отсутствие защитной каски</b>" in caption_new
    assert "Камера цеха №1" in caption_new
    assert "Сборочный сектор" in caption_new

    # Проверка с обновленным статусом
    event["status"] = "acknowledged"
    event["assigned_to"] = "Петров С."
    caption_ack = mock_telegram_client.format_caption(event)
    assert "Принято в работу" in caption_ack
    assert "Петров С." in caption_ack


def test_telegram_keyboard_generation(mock_telegram_client):
    event = {"id": "inc_42", "status": "new"}
    kb = mock_telegram_client.make_keyboard(event)
    rows = kb["inline_keyboard"]
    assert len(rows) == 3
    assert rows[0][0]["callback_data"] == "st:inc_42:c"
    assert rows[0][1]["callback_data"] == "st:inc_42:f"
    assert rows[1][0]["callback_data"] == "st:inc_42:w"
    assert rows[2][0]["url"] == "http://dashboard.local"

    # Для завершенного инцидента клавиатура пустая
    event_done = {"id": "inc_42", "status": "resolved"}
    assert mock_telegram_client.make_keyboard(event_done) == {"inline_keyboard": []}


def test_telegram_on_command_dispatch(mock_telegram_client, temp_store):
    msg = {
        "chat": {"id": 555, "type": "private", "first_name": "Инженер"},
        "from": {"id": 1, "username": "eng"},
    }

    # /start
    mock_telegram_client.send_message = MagicMock()
    mock_telegram_client.on_command(msg, "/start", "")
    assert temp_store.get_subscriber("telegram", 555) is not None
    mock_telegram_client.send_message.assert_called_once()

    # /level
    mock_telegram_client.send_message.reset_mock()
    mock_telegram_client.on_command(msg, "/level", "high")
    assert temp_store.get_subscriber("telegram", 555)["min_severity"] == "high"

    # /level invalid
    mock_telegram_client.send_message.reset_mock()
    mock_telegram_client.on_command(msg, "/level", "super_extreme")
    assert "Использование" in mock_telegram_client.send_message.call_args[0][1]

    # /stop
    mock_telegram_client.on_command(msg, "/stop", "")
    assert temp_store.get_subscriber("telegram", 555)["active"] == 0


def test_telegram_on_callback_handler(mock_telegram_client):
    status_calls = []
    mock_telegram_client.on_status_change = lambda eid, st, op: status_calls.append((eid, st, op))
    mock_telegram_client.api = MagicMock()

    cq = {
        "id": "query_123",
        "data": "st:event_99:f",
        "from": {"username": "ivanov"},
    }
    mock_telegram_client.on_callback(cq)
    assert len(status_calls) == 1
    assert status_calls[0] == ("event_99", "false_positive", "ivanov")
    mock_telegram_client.api.assert_called_with(
        "answerCallbackQuery",
        {"callback_query_id": "query_123", "text": "Статус обновлен: ✖️ Ложная тревога"},
    )


# ==============================================================================
# 4. NotificationManager Tests
# ==============================================================================

def test_notification_manager_dispatch_and_severity_filtering(tmp_path):
    mgr = NotificationManager()
    mgr.store = NotificationStore(str(tmp_path / "mgr_test.db"))

    # Подписчик 1: порог critical
    mgr.store.upsert_subscriber("telegram", "chat_crit", "Руководство", "channel")
    mgr.store.update_subscriber(1, min_severity="critical")

    # Подписчик 2: порог low (получает всё)
    mgr.store.upsert_subscriber("telegram", "chat_all", "Диспетчерская", "group")
    mgr.store.update_subscriber(2, min_severity="low")

    # Мокаем отправку Telegram
    mgr.telegram.token = "VALID_TOKEN"
    mgr.telegram.send_alert = MagicMock(return_value=("msg_10", "text"))

    # 1. Инцидент низкой важности (low)
    low_inc = {"id": "1", "severity": "low", "rule_name": "phone_usage"}
    mgr._deliver_incident(low_inc)
    # Должен уйти только в chat_all
    assert mgr.telegram.send_alert.call_count == 1
    called_chat = mgr.telegram.send_alert.call_args[0][0]["chat_id"]
    assert called_chat == "chat_all"

    # 2. Инцидент высокой важности (critical)
    mgr.telegram.send_alert.reset_mock()
    crit_inc = {"id": "2", "severity": "critical", "rule_name": "fall"}
    mgr._deliver_incident(crit_inc)
    # Должен уйти в оба чата
    assert mgr.telegram.send_alert.call_count == 2


def test_notification_manager_retry_on_failure(tmp_path):
    mgr = NotificationManager()
    mgr.store = NotificationStore(str(tmp_path / "retry_test.db"))
    sub = mgr.store.upsert_subscriber("telegram", "chat_retry", "Retry Team", "group")

    mgr.telegram.token = "VALID_TOKEN"

    # Имитируем сбой 2 раза, затем успех
    attempts = [0]

    def mock_send(sub, ev, snap):
        attempts[0] += 1
        if attempts[0] < 3:
            raise ApiError("Network glitch", 500)
        return "msg_success", "text"

    mgr.telegram.send_alert = mock_send

    success = mgr._send_with_retry(mgr.telegram, sub, {"id": "inc_retry"})
    assert success is True
    assert attempts[0] == 3
    deliveries = mgr.store.get_deliveries_for_event("inc_retry")
    assert len(deliveries) == 1
    assert deliveries[0]["message_id"] == "msg_success"


def test_telegram_resolve_action_and_working_keyboard(mock_telegram_client):
    """Проверка кнопок и callback устранения (resolved) для инцидента в работе."""
    # Клавиатура для инцидента в статусе 'working' должна содержать кнопку 'Устранено' и 'Ложное'
    event_working = {"id": "inc_99", "status": "working"}
    kb = mock_telegram_client.make_keyboard(event_working)
    rows = kb["inline_keyboard"]
    assert len(rows) >= 1
    assert rows[0][0]["callback_data"] == "st:inc_99:r"
    assert "Устранено" in rows[0][0]["text"]
    assert rows[0][1]["callback_data"] == "st:inc_99:f"

    # Callback 'r' должен вызывать on_status_change со статусом 'resolved'
    status_calls = []
    mock_telegram_client.on_status_change = lambda eid, st, op: status_calls.append((eid, st, op))
    mock_telegram_client.api = MagicMock()

    cq = {
        "id": "query_resolve",
        "data": "st:inc_99:r",
        "from": {"username": "safety_officer"},
    }
    mock_telegram_client.on_callback(cq)
    assert len(status_calls) == 1
    assert status_calls[0] == ("inc_99", "resolved", "safety_officer")


def test_store_list_deliveries(temp_store):
    """Проверка фильтрации и выборки журнала доставок и ошибок."""
    temp_store.add_delivery("TK-01", "telegram", "123", "msg_1", "photo", ok=True, latency_ms=120)
    temp_store.add_delivery("TK-02", "telegram", "123", None, "failed", ok=False, error="Connection timeout")

    all_delivs = temp_store.list_deliveries(limit=10)
    assert len(all_delivs) == 2

    failed_only = temp_store.list_deliveries(failed_only=True)
    assert len(failed_only) == 1
    assert failed_only[0]["event_id"] == "TK-02"
    assert "timeout" in failed_only[0]["error"]


def test_notification_snapshot_resolution_from_video_processing(tmp_path):
    """Синхронизация оповещений с видеообработкой: проверка резолвинга стоп-кадра из storage."""
    mgr = NotificationManager()
    mgr.store = NotificationStore(str(tmp_path / "video_sync.db"))
    sub = mgr.store.upsert_subscriber("telegram", "chat_video_ops", "Дежурная смена", "group")

    # Создаем тестовый стоп-кадр на диске в подпапке даты
    snap_dir = tmp_path / "snapshots" / "2026-10-25"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_file = snap_dir / "inc_TK-VIDEO-01_CAM-01.jpg"
    snap_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    # Имитируем инцидент, созданный воркером видеопотока
    video_event = {
        "id": "TK-VIDEO-01",
        "camera_id": "CAM-01",
        "camera_name": "Xiaomi 360 (Сборочный участок)",
        "zone": "Цех № 1",
        "title": "Сотрудник без каски в рабочей зоне",
        "severity": "critical",
        "snapshot_path": "/static/snapshots/2026-10-25/inc_TK-VIDEO-01_CAM-01.jpg",
        "image_key": "/static/snapshots/2026-10-25/inc_TK-VIDEO-01_CAM-01.jpg",
    }

    mgr.telegram.token = "VALID_TOKEN"
    calls = []
    def mock_send(subscriber, event, snap_path):
        calls.append((subscriber["chat_id"], event["id"], snap_path))
        return "msg_123", "photo"

    mgr.telegram.send_alert = mock_send

    with patch("app.services.notifications.manager.settings.LOCAL_SNAPSHOTS_DIR", str(tmp_path / "snapshots")), \
         patch("app.services.notifications.manager.BASE_DIR", tmp_path):
        mgr._deliver_incident(video_event, video_event["snapshot_path"])

    assert len(calls) == 1
    chat_id, eid, actual_snap = calls[0]
    assert chat_id == "chat_video_ops"
    assert eid == "TK-VIDEO-01"
    assert actual_snap is not None
    assert os.path.normpath(actual_snap) == os.path.normpath(str(snap_file))


def test_single_alert_for_prolonged_violation(tmp_path):
    """
    Проверка требования: при начале нарушения отсылается ровно один алерт.
    Если нарушение продолжается (продолжительное), повторные алерты не отправляются.
    Новый алерт шлется только после прекращения/устранения предыдущего.
    """
    mgr = NotificationManager()
    mgr.store = NotificationStore(str(tmp_path / "prolonged_test.db"))

    inc1 = {
        "id": "TK-P1",
        "camera_id": "CAM-01",
        "title": "Сотрудник без каски",
        "severity": "high",
    }
    inc2 = {
        "id": "TK-P2",
        "camera_id": "CAM-01",
        "title": "Сотрудник без каски",
        "severity": "high",
    }

    # 1. Начало нарушения — ставится задача на рассылку нового алерта
    mgr.dispatch_incident(inc1)
    task1 = mgr.q.get_nowait()
    assert task1["kind"] == "incident"
    assert task1["event"]["id"] == "TK-P1"

    # 2. Нарушение продолжается — повторный вызов НЕ создает второй алерт, а обновляет текущий
    mgr.dispatch_incident(inc2)
    task2 = mgr.q.get_nowait()
    assert task2["kind"] == "incident_update"
    assert task2["event"]["id"] == "TK-P2"

    # 3. Инцидент устранен (resolved)
    mgr.update_incident_status("TK-P2", "resolved")
    status_task = mgr.q.get_nowait()
    assert status_task["kind"] == "status_update"

    # 4. Спустя время нарушение начинается снова — должен уйти новый алерт
    inc3 = {
        "id": "TK-P3",
        "camera_id": "CAM-01",
        "title": "Сотрудник без каски",
        "severity": "high",
    }
    mgr.dispatch_incident(inc3)
    task3 = mgr.q.get_nowait()
    assert task3["kind"] == "incident"
    assert task3["event"]["id"] == "TK-P3"



