"""Ядро уведомлений: подписчики (чаты), рассылка, повторы, обновление сообщений по статусу."""
import html
import logging
import os
import queue
import sqlite3
import threading
import time

from .. import config
from .netio import ApiError

SEV = {"low": 0, "medium": 1, "high": 2, "critical": 3}
SEV_ICON = {"critical": "🚨", "high": "🔶", "medium": "🟡", "low": "⚪"}
STATUS_TEXT = {"confirmed": "✅ подтверждено", "false": "✖️ ложное срабатывание", "forwarded": "👷 принято в работу"}
logger = logging.getLogger("linq.notify")


def log(*a):
    logger.info("%s", " ".join(str(value) for value in a))


class NotifyStore:
    def __init__(self, path=None):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        self.db = sqlite3.connect(path or os.path.join(config.DATA_DIR, "notify.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS subscribers(
              id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, chat_id TEXT, title TEXT, kind TEXT,
              min_severity TEXT DEFAULT 'low', active INTEGER DEFAULT 1, added_by TEXT, added_ts REAL,
              UNIQUE(channel, chat_id));
            CREATE TABLE IF NOT EXISTS deliveries(
              id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, channel TEXT, chat_id TEXT,
              message_id TEXT, kind TEXT, ok INTEGER, error TEXT, sent_ts REAL, latency_ms REAL);
            CREATE INDEX IF NOT EXISTS ix_del_ev ON deliveries(event_id);""")
            self.db.commit()

    def _rows(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def upsert_sub(self, channel, chat_id, title, kind, added_by=None):
        chat_id = str(chat_id)
        with self.lock:
            self.db.execute(
                "INSERT INTO subscribers(channel,chat_id,title,kind,added_by,added_ts) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(channel,chat_id) DO UPDATE SET active=1, title=excluded.title, kind=excluded.kind",
                (channel, chat_id, title, kind, added_by, time.time()))
            self.db.commit()
        return self._rows("SELECT * FROM subscribers WHERE channel=? AND chat_id=?", (channel, chat_id))[0]

    def subs(self, channel=None, active=None):
        where, args = [], []
        if channel:
            where.append("channel=?"); args.append(channel)
        if active is not None:
            where.append("active=?"); args.append(int(active))
        return self._rows("SELECT * FROM subscribers" + (" WHERE " + " AND ".join(where) if where else "")
                          + " ORDER BY id", args)

    def get_sub(self, channel, chat_id):
        r = self._rows("SELECT * FROM subscribers WHERE channel=? AND chat_id=?", (channel, str(chat_id)))
        return r[0] if r else None

    def update_sub(self, sid, **f):
        f = {k: v for k, v in f.items() if k in ("active", "min_severity", "title")}
        if not f:
            return
        with self.lock:
            self.db.execute("UPDATE subscribers SET " + ",".join(f"{k}=?" for k in f) + " WHERE id=?",
                            (*[int(v) if k == "active" else v for k, v in f.items()], sid))
            self.db.commit()

    def set_active(self, channel, chat_id, active):
        with self.lock:
            self.db.execute("UPDATE subscribers SET active=? WHERE channel=? AND chat_id=?",
                            (int(active), channel, str(chat_id)))
            self.db.commit()

    def move_chat(self, channel, old, new):
        with self.lock:
            self.db.execute("UPDATE subscribers SET chat_id=? WHERE channel=? AND chat_id=?", (str(new), channel, str(old)))
            self.db.commit()

    def delete_sub(self, sid):
        with self.lock:
            self.db.execute("DELETE FROM subscribers WHERE id=?", (sid,))
            self.db.commit()

    def add_delivery(self, event_id, channel, chat_id, message_id, kind, ok, error=None, latency_ms=None):
        with self.lock:
            self.db.execute("INSERT INTO deliveries(event_id,channel,chat_id,message_id,kind,ok,error,sent_ts,latency_ms)"
                            " VALUES(?,?,?,?,?,?,?,?,?)",
                            (event_id, channel, str(chat_id), None if message_id is None else str(message_id),
                             kind, int(ok), error, time.time(), latency_ms))
            self.db.commit()

    def deliveries_for(self, event_id, channel=None):
        return self._rows("SELECT * FROM deliveries WHERE event_id=? AND ok=1" + (" AND channel=?" if channel else ""),
                          (event_id, channel) if channel else (event_id,))

    def delivery_stats(self):
        out = {}
        for r in self._rows("SELECT channel, ok, COUNT(*) n, AVG(latency_ms) lat FROM deliveries GROUP BY channel, ok"):
            d = out.setdefault(r["channel"], {"ok": 0, "failed": 0, "avg_ms": None})
            d["ok" if r["ok"] else "failed"] = r["n"]
            if r["ok"]:
                d["avg_ms"] = round(r["lat"], 1) if r["lat"] is not None else None
        return out


def fmt_time(ts):
    return time.strftime("%d.%m %H:%M:%S", time.localtime(ts))


def alert_lines(ev):
    """Данные сообщения без разметки; каналы сами оформляют их (HTML, обычный текст)."""
    where = f"Камера: {ev['camera']}" + (f" · Зона: {ev['zone']}" if ev.get("zone") else "")
    return (f"{SEV_ICON.get(ev['severity'], '⚪')} {ev['label']}", where,
            f"Время: {fmt_time(ev['ts'])} · человек #{ev['track_id']} · событие №{ev['id']}")


def status_line(ev):
    if ev.get("status") in STATUS_TEXT:
        who = f" — {ev['handled_by']}" if ev.get("handled_by") else ""
        when = time.strftime("%H:%M", time.localtime(ev["handled_ts"])) if ev.get("handled_ts") else ""
        return f"{STATUS_TEXT[ev['status']]}{who} {when}".strip()
    return ""


class Notifier:
    retry_delay = 2.0

    def __init__(self, events, hub, nstore=None, public_url=None):
        self.events, self.hub = events, hub
        self.store = nstore or NotifyStore()
        self.public_url = public_url or os.environ.get("LINQ_PUBLIC_URL")
        self.clients, self._stop = {}, False
        self.q = None

    def add_client(self, client):
        self.clients[client.channel] = client

    def start(self):
        self.q = self.hub.subscribe()
        threading.Thread(target=self._loop, daemon=True, name="notify-dispatch").start()
        for c in self.clients.values():
            threading.Thread(target=c.run, daemon=True, name=f"notify-{c.channel}").start()

    def stop(self):
        self._stop = True
        for c in self.clients.values():
            c.stop()

    # --- действия из чатов
    def set_status(self, eid, status, by):
        ev = self.events.set_status(eid, status, by)
        if ev:
            self.hub.publish({"kind": "status", "event": ev})
        return ev

    def register(self, channel, chat_id, title, kind, by=None):
        sub = self.store.upsert_sub(channel, chat_id, title, kind, by)
        logger.info("subscriber_connected channel=%s kind=%s", channel, kind)
        self.hub.publish({"kind": "notify"})
        return sub

    def unregister(self, channel, chat_id):
        self.store.set_active(channel, chat_id, False)
        logger.info("subscriber_disconnected channel=%s", channel)
        self.hub.publish({"kind": "notify"})

    def summary(self):
        s = self.events.dashboard(since=time.time() - 86400)
        return (f"За 24 часа нарушений: {s['total']}, критических: {s['critical']}, "
                f"ждут проверки: {s['pending']}. Камер: {len(self.hub.perf)}.")

    # --- рассылка
    def _loop(self):
        while not self._stop:
            try:
                msg = self.q.get(timeout=1)
            except queue.Empty:
                continue
            try:
                if msg["kind"] == "event":
                    self.deliver(msg["event"])
                elif msg["kind"] == "status":
                    self.refresh_messages(msg["event"])
            except Exception as e:                      # рассылка не должна падать целиком
                logger.error("notification_dispatch_failed error_type=%s", type(e).__name__)

    def deliver(self, ev, only=None, test=False):
        snap = os.path.join(config.SNAP_DIR, ev["snapshot"]) if ev.get("snapshot") else None
        for sub in self.store.subs(active=True):
            if only and sub["id"] != only:
                continue
            c = self.clients.get(sub["channel"])
            if c and (test or SEV[ev["severity"]] >= SEV.get(sub["min_severity"], 0)):
                self._send(c, sub, ev, snap)

    def _send(self, client, sub, ev, snap):
        err = None
        err_type = "unknown"
        for attempt in range(3):
            t0 = time.perf_counter()
            try:
                mid, kind = client.send_alert(sub, ev, snap)
                self.store.add_delivery(ev["id"], client.channel, sub["chat_id"], mid, kind, True,
                                        latency_ms=(time.perf_counter() - t0) * 1e3)
                return True
            except ApiError as e:
                err = str(e)
                err_type = type(e).__name__
                if client.is_gone(e):
                    self.store.set_active(client.channel, sub["chat_id"], False)
                    break
                if attempt < 2:
                    time.sleep(min(e.retry_after or self.retry_delay * (attempt + 1), 30))
        self.store.add_delivery(ev["id"], client.channel, sub["chat_id"], None, None, False, err)
        logger.error("notification_failed event_id=%s channel=%s error_type=%s",
                     ev["id"], client.channel, err_type)
        return False

    def refresh_messages(self, ev):
        for d in self.store.deliveries_for(ev["id"]):
            c = self.clients.get(d["channel"])
            if c and d["message_id"]:
                try:
                    c.update_alert(d, ev)
                except ApiError as e:
                    logger.warning("notification_update_failed event_id=%s channel=%s error_type=%s",
                                   ev["id"], d["channel"], type(e).__name__)

    def send_test(self, sub_id=None):
        ev = {"id": 0, "ts": time.time(), "camera": "cam-test", "type": "test", "label": "Тестовое оповещение",
              "severity": "low", "zone": None, "track_id": 0, "status": "test", "snapshot": None}
        subs = [s for s in self.store.subs(active=True) if not sub_id or s["id"] == sub_id]
        for s in subs:
            c = self.clients.get(s["channel"])
            if c:
                self._send(c, s, ev, None)
        return len(subs)

    # --- для интерфейса
    def info(self):
        chans = {name: c.info() for name, c in self.clients.items()}
        return {"channels": chans, "subscribers": self.store.subs(), "stats": self.store.delivery_stats(),
                "public_url": self.public_url}


def load_env(path=".env"):
    """Мини-загрузчик .env: KEY=VALUE, без зависимостей."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


def from_env(events, hub):
    from .telegram import Telegram
    load_env(os.path.join(config.ROOT, ".env"))
    n = Notifier(events, hub)
    if os.environ.get("LINQ_TG_TOKEN"):
        n.add_client(Telegram(os.environ["LINQ_TG_TOKEN"], n, os.environ.get("LINQ_TG_API", "https://api.telegram.org")))
    return n
