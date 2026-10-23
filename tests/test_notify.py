"""Тесты уведомлений Telegram на поддельном сервере (реальная сеть не нужна)."""
import json, os, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
os.environ["LINQ_DATA"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config
from app.hub import Hub
from app.store import EventStore
from app.notify.core import Notifier, NotifyStore
from app.notify.telegram import Telegram


class Fake:
    """HTTP-сервер имитирует Telegram Bot API и загрузку фото."""
    def __init__(self):
        self.calls, self.tg_updates = [], []
        fake = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"
            def log_message(self, *a): pass
            def reply(self, obj):
                b = json.dumps(obj).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0); raw = self.rfile.read(n)
                path = self.path
                if "multipart" in (self.headers.get("Content-Type") or ""):
                    fake.calls.append((path, {"_raw": raw})); 
                    if "upload" in path: return self.reply({"server": 1, "photo": "p", "hash": "h"})
                    return self.reply({"ok": True, "result": {"message_id": 77}})
                if path.startswith("/bot"):
                    method = path.rsplit("/", 1)[1]; body = json.loads(raw or b"{}")
                    fake.calls.append((method, body))
                    if method == "getMe": return self.reply({"ok": True, "result": {"username": "linq_bot"}})
                    if method == "getUpdates":
                        u, fake.tg_updates = fake.tg_updates, []
                        if not u: time.sleep(.15)
                        return self.reply({"ok": True, "result": u})
                    if method == "sendMessage": return self.reply({"ok": True, "result": {"message_id": 5}})
                    return self.reply({"ok": True, "result": True})
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H); self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def of(self, method): return [b for m, b in self.calls if m == method]


def wait(cond, t=6.0):
    end = time.time() + t
    while time.time() < end:
        if cond(): return True
        time.sleep(.05)
    return False


def make_event(store, **kw):
    ev = {"ts": time.time(), "camera": "cam1", "type": "fall", "label": "Падение или неподвижность", "severity": "critical",
          "zone": "Склад", "track_id": 3, "status": "new", "snapshot": "x.jpg", "latency_ms": 5.0, **kw}
    ev["id"] = store.add(ev); return ev


class NotifyTest(unittest.TestCase):
    def setUp(self):
        self.fake = Fake(); self.hub = Hub(); self.events = EventStore(os.path.join(config.DATA_DIR, f"e{time.time()}.db"))
        self.n = Notifier(self.events, self.hub, NotifyStore(os.path.join(config.DATA_DIR, f"n{time.time()}.db")))
        self.n.retry_delay = .05
        os.makedirs(config.SNAP_DIR, exist_ok=True)
        open(os.path.join(config.SNAP_DIR, "x.jpg"), "wb").write(b"\xff\xd8fakejpeg")

    def tearDown(self): self.n.stop(); self.fake.srv.shutdown()

    def test_telegram_group_flow(self):
        self.n.add_client(Telegram("TOKEN", self.n, f"http://127.0.0.1:{self.fake.port}")); self.n.start()
        self.assertTrue(wait(lambda: self.n.clients["telegram"].status == "online"))
        self.assertEqual(self.n.info()["channels"]["telegram"]["links"]["group"], "https://t.me/linq_bot?startgroup=linq")
        # бота добавили в супергруппу -> чат зафиксирован сам
        self.fake.tg_updates.append({"update_id": 1, "my_chat_member": {"chat": {"id": -1001, "type": "supergroup", "title": "Смена А"},
            "from": {"id": 7, "username": "master"}, "new_chat_member": {"status": "member"}}})
        self.assertTrue(wait(lambda: self.n.store.subs(active=True)))
        self.assertEqual(self.n.store.subs()[0]["chat_id"], "-1001")
        # событие -> фото в чат с кнопками
        ev = make_event(self.events); self.hub.publish({"kind": "event", "event": ev})
        self.assertTrue(wait(lambda: any(m == "/bot" or "sendPhoto" in m for m, _ in self.fake.calls)))
        raw = [b for m, b in self.fake.calls if "sendPhoto" in m][0]["_raw"]
        self.assertIn("Падение".encode(), raw); self.assertIn(b"st:%d:c" % ev["id"], raw); self.assertIn(b"-1001", raw)
        # нажали «Подтвердить» -> статус в БД с автором, сообщение обновилось
        self.fake.tg_updates.append({"update_id": 2, "callback_query": {"id": "cb1", "data": f"st:{ev['id']}:c",
            "from": {"id": 8, "username": "ivanov"}, "message": {"message_id": 77, "chat": {"id": -1001}}}})
        self.assertTrue(wait(lambda: self.events.get(ev["id"])["status"] == "confirmed"))
        self.assertEqual(self.events.get(ev["id"])["handled_by"], "@ivanov")
        self.assertTrue(wait(lambda: self.fake.of("editMessageCaption")))
        self.assertIn("подтверждено", self.fake.of("editMessageCaption")[0]["caption"])
        self.assertEqual(self.fake.of("editMessageCaption")[0]["reply_markup"], {"inline_keyboard": []})
        # порог важности: low-событие не должно прийти после /level critical
        self.fake.tg_updates.append({"update_id": 3, "message": {"text": "/level critical", "chat": {"id": -1001, "type": "supergroup", "title": "Смена А"}, "from": {"id": 7}}})
        self.assertTrue(wait(lambda: self.n.store.subs()[0]["min_severity"] == "critical"))
        before = len([m for m, _ in self.fake.calls if "sendPhoto" in m])
        self.hub.publish({"kind": "event", "event": make_event(self.events, type="phone", severity="low", label="Телефон")})
        time.sleep(.5); self.assertEqual(len([m for m, _ in self.fake.calls if "sendPhoto" in m]), before)
        # бота удалили -> чат отключён
        self.fake.tg_updates.append({"update_id": 4, "my_chat_member": {"chat": {"id": -1001, "type": "supergroup", "title": "x"},
            "from": {"id": 7}, "new_chat_member": {"status": "kicked"}}})
        self.assertTrue(wait(lambda: not self.n.store.subs(active=True)))
        self.assertEqual(self.n.store.delivery_stats()["telegram"]["ok"], 1)

    def test_failed_delivery_is_recorded(self):
        class Bad:
            channel = "telegram"
            def send_alert(self, *a): raise __import__("app.notify.netio", fromlist=["x"]).ApiError("boom", 500)
            def is_gone(self, e): return False
            def run(self): pass
            def stop(self): pass
            def info(self): return {}
        self.n.add_client(Bad()); self.n.store.upsert_sub("telegram", "1", "t", "private")
        ev = make_event(self.events)
        self.assertFalse(self.n._send(self.n.clients["telegram"], self.n.store.subs()[0], ev, None))
        self.assertEqual(self.n.store.delivery_stats()["telegram"]["failed"], 1)


class DashboardTest(unittest.TestCase):
    def test_reaction_time_and_series(self):
        st = EventStore(os.path.join(config.DATA_DIR, f"d{time.time()}.db"))
        now = time.time()
        a = make_event(st, ts=now - 120); b = make_event(st, ts=now - 60, type="phone", severity="low"); make_event(st, ts=now - 10)
        st.set_status(a["id"], "confirmed", "@m"); st.set_status(b["id"], "false", "@m")
        d = st.dashboard(since=now - 3600)
        self.assertEqual((d["total"], d["pending"]), (3, 1))
        self.assertEqual(d["precision"], 0.5)
        self.assertGreater(d["reaction_s"]["avg"], 50)
        self.assertEqual(sum(sum(b["counts"].values()) for b in d["series"]["buckets"]), 3)
        self.assertEqual(sum(map(sum, d["heatmap"])), 3)


if __name__ == "__main__":
    unittest.main()
