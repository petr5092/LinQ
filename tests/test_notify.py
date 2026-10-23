"""
Тесты системы оперативного оповещения Telegram и NotificationStore на поддельном сервере.
"""

import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.services.notifications.manager import NotificationManager
from app.services.notifications.store import NotificationStore
from app.services.notifications.telegram import TelegramClient


class FakeTelegramServer:
    """HTTP-сервер, имитирующий Telegram Bot API в памяти."""

    def __init__(self):
        self.calls = []
        self.tg_updates = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *a):
                pass

            def reply(self, obj):
                b = json.dumps(obj).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n)
                path = self.path

                if "multipart" in (self.headers.get("Content-Type") or ""):
                    fake.calls.append((path, {"_raw": raw}))
                    return self.reply({"ok": True, "result": {"message_id": 77}})

                if path.startswith("/bot"):
                    method = path.rsplit("/", 1)[1]
                    body = json.loads(raw.decode("utf-8") or "{}")
                    fake.calls.append((method, body))

                    if method == "getMe":
                        return self.reply({"ok": True, "result": {"username": "linq_test_bot"}})
                    if method == "getUpdates":
                        u, fake.tg_updates = fake.tg_updates, []
                        if not u:
                            time.sleep(0.05)
                        return self.reply({"ok": True, "result": u})
                    if method == "sendMessage":
                        return self.reply({"ok": True, "result": {"message_id": 5}})
                    return self.reply({"ok": True, "result": True})

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def of(self, method):
        return [b for m, b in self.calls if m == method]


def wait_until(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class TestTelegramNotification(unittest.TestCase):
    def setUp(self):
        self.fake = FakeTelegramServer()
        self.temp_db = tempfile.mktemp(suffix=".db")
        self.store = NotificationStore(self.temp_db)

        self.status_changes = []

        def on_status_change(eid, status, op):
            self.status_changes.append((eid, status, op))

        self.tg = TelegramClient(
            token="TEST_TOKEN",
            store=self.store,
            base_url=f"http://127.0.0.1:{self.fake.port}",
            on_status_change=on_status_change,
        )

    def tearDown(self):
        self.tg.stop()
        self.fake.srv.shutdown()
        if os.path.exists(self.temp_db):
            try:
                os.remove(self.temp_db)
            except OSError:
                pass

    def test_telegram_subscription_and_alerts(self):
        self.tg.start()
        self.assertTrue(wait_until(lambda: self.tg.status == "online"))
        self.assertEqual(self.tg.username, "linq_test_bot")

        # 1. Добавление бота в группу: my_chat_member
        self.fake.tg_updates.append({
            "update_id": 1,
            "my_chat_member": {
                "chat": {"id": -1001, "type": "supergroup", "title": "Смена 1"},
                "from": {"id": 10, "username": "shift_lead"},
                "new_chat_member": {"status": "member"},
            },
        })

        self.assertTrue(wait_until(lambda: len(self.store.list_subscribers(active=True)) == 1))
        sub = self.store.list_subscribers()[0]
        self.assertEqual(sub["chat_id"], "-1001")
        self.assertEqual(sub["title"], "Смена 1")

        # 2. Отправка алерта
        ev = {
            "id": "inc_001",
            "rule_name": "danger_zone",
            "rule_label": "Вход в опасную зону",
            "severity": "critical",
            "camera_name": "Камера ворот",
            "zone_name": "Зона разгрузки",
            "status": "new",
        }
        msg_id, kind = self.tg.send_alert(sub, ev)
        self.assertEqual(msg_id, "5")
        self.assertEqual(kind, "text")

        # 3. Нажатие кнопки подтверждения: callback_query
        self.fake.tg_updates.append({
            "update_id": 2,
            "callback_query": {
                "id": "cb_01",
                "data": "st:inc_001:c",
                "from": {"id": 15, "username": "ivanov_op"},
                "message": {"message_id": 5, "chat": {"id": -1001}},
            },
        })

        self.assertTrue(wait_until(lambda: len(self.status_changes) == 1))
        self.assertEqual(self.status_changes[0], ("inc_001", "confirmed", "ivanov_op"))

        # 4. Команда /level critical
        self.fake.tg_updates.append({
            "update_id": 3,
            "message": {
                "text": "/level critical",
                "chat": {"id": -1001, "type": "supergroup"},
                "from": {"id": 10},
            },
        })

        self.assertTrue(wait_until(lambda: self.store.get_subscriber("telegram", -1001)["min_severity"] == "critical"))


if __name__ == "__main__":
    unittest.main()
