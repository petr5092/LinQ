"""Журнал событий (SQLite) и хранилище зон (JSON)."""
import json
import os
import sqlite3
import threading
import time

from . import config
from .enterprise import UNASSIGNED_SHIFT

STATUSES = ("new", "confirmed", "false", "forwarded")
EVENT_MERGE_WINDOW_SECONDS = 300
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class EventStore:
    def __init__(self, path=None):
        data_dir = os.environ.get("LINQ_DATA", config.DATA_DIR)
        os.makedirs(data_dir, exist_ok=True)
        self.db = sqlite3.connect(path or os.path.join(data_dir, "events.db"),
                                  check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, camera TEXT, type TEXT, label TEXT,
                severity TEXT, zone TEXT, track_id INTEGER, status TEXT, snapshot TEXT, latency_ms REAL,
                workshop TEXT, shift TEXT, shift_date TEXT)""")
            self.db.execute("CREATE INDEX IF NOT EXISTS ix_ts ON events(ts)")
            cols = {r[1] for r in self.db.execute("PRAGMA table_info(events)")}
            for col, typ in (("handled_ts", "REAL"), ("handled_by", "TEXT"), ("workshop", "TEXT"),
                             ("shift", "TEXT"), ("shift_date", "TEXT")):
                if col not in cols:
                    self.db.execute(f"ALTER TABLE events ADD COLUMN {col} {typ}")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS event_history(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    changed_ts REAL NOT NULL,
                    actor TEXT NOT NULL,
                    old_status TEXT NOT NULL,
                    new_status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_history_event ON event_history(event_id, id);
                CREATE TRIGGER IF NOT EXISTS event_history_no_update
                BEFORE UPDATE ON event_history
                BEGIN SELECT RAISE(ABORT, 'event history is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS event_history_no_delete
                BEFORE DELETE ON event_history
                BEGIN SELECT RAISE(ABORT, 'event history is append-only'); END;
            """)
            self.db.commit()

    def add(self, ev):
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute(
                "SELECT * FROM events WHERE camera=? AND type=? AND status='new' AND ts>=? "
                "ORDER BY ts DESC, id DESC LIMIT 1",
                (ev["camera"], ev["type"], ev["ts"] - EVENT_MERGE_WINDOW_SECONDS),
            ).fetchone()
            if existing:
                severity = max(
                    (existing["severity"], ev["severity"]),
                    key=lambda value: SEVERITY_RANK.get(value, 0),
                )
                self.db.execute(
                    "UPDATE events SET ts=?, label=?, severity=?, zone=?, track_id=?, snapshot=?, latency_ms=?, "
                    "workshop=?, shift=?, shift_date=? WHERE id=?",
                    (ev["ts"], ev["label"], severity, ev["zone"], ev["track_id"], ev["snapshot"], ev["latency_ms"],
                     ev.get("workshop"), ev.get("shift"), ev.get("shift_date"), existing["id"]),
                )
                ev.update(id=existing["id"], severity=severity, merged=True)
                return existing["id"]
            cur = self.db.execute(
                "INSERT INTO events(ts,camera,type,label,severity,zone,track_id,status,snapshot,latency_ms,"
                "workshop,shift,shift_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ev["ts"], ev["camera"], ev["type"], ev["label"], ev["severity"], ev["zone"],
                 ev["track_id"], ev["status"], ev["snapshot"], ev["latency_ms"],
                 ev.get("workshop"), ev.get("shift"), ev.get("shift_date")))
            ev.update(id=cur.lastrowid, merged=False)
            return cur.lastrowid

    def query(self, type=None, camera=None, zone=None, status=None, since=None, until=None, limit=200,
              workshop=None, shift=None):
        where, args = [], []
        for col, val in (("type", type), ("camera", camera), ("zone", zone), ("status", status),
                         ("workshop", workshop), ("shift", shift)):
            if val:
                where.append(f"{col}=?")
                args.append(val)
        if since:
            where.append("ts>=?")
            args.append(float(since))
        if until:
            where.append("ts<=?")
            args.append(float(until))
        sql = "SELECT * FROM events" + (" WHERE " + " AND ".join(where) if where else "") \
              + " ORDER BY ts DESC, id DESC LIMIT ?"
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, (*args, int(limit))).fetchall()]

    def set_status(self, eid, status, by=None):
        if status not in STATUSES:
            return None
        actor = str(by or "Не указан").strip()[:120] or "Не указан"
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            current = self.db.execute("SELECT status FROM events WHERE id=?", (eid,)).fetchone()
            if current is None:
                return None
            old_status = current["status"]
            if old_status != status:
                changed_ts = time.time()
                self.db.execute("UPDATE events SET status=?, handled_ts=?, handled_by=? WHERE id=?",
                                (status, None if status == "new" else changed_ts, actor, eid))
                self.db.execute(
                    "INSERT INTO event_history(event_id,changed_ts,actor,old_status,new_status) VALUES(?,?,?,?,?)",
                    (eid, changed_ts, actor, old_status, status))
            r = self.db.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
        return dict(r) if r else None

    def history(self, eid):
        with self.lock:
            return [dict(r) for r in self.db.execute(
                "SELECT id,event_id,changed_ts,actor,old_status,new_status "
                "FROM event_history WHERE event_id=? ORDER BY id", (eid,)).fetchall()]

    def get(self, eid):
        with self.lock:
            r = self.db.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
        return dict(r) if r else None

    def stats(self):
        with self.lock:
            rows = [dict(r) for r in self.db.execute("SELECT * FROM events").fetchall()]
        def count(key, fallback=None):
            d = {}
            for r in rows:
                value = r[key] or fallback
                if value:
                    d[value] = d.get(value, 0) + 1
            return d
        hours = [0] * 24
        for r in rows:
            hours[time.localtime(r["ts"]).tm_hour] += 1
        decided = sum(1 for r in rows if r["status"] in ("confirmed", "false"))
        false_n = sum(1 for r in rows if r["status"] == "false")
        return {"total": len(rows), "critical": sum(1 for r in rows if r["severity"] == "critical"),
                "by_type": count("type"), "by_camera": count("camera"), "by_zone": count("zone"),
                "by_status": count("status"), "by_hour": hours,
                "false_rate": (false_n / decided) if decided else None}


    def dashboard(self, since=None, until=None):
        """Все данные для дашбордов за период одним запросом."""
        where, args = [], []
        if since:
            where.append("ts>=?"); args.append(float(since))
        if until:
            where.append("ts<=?"); args.append(float(until))
        sql = "SELECT * FROM events" + (" WHERE " + " AND ".join(where) if where else "")
        with self.lock:
            rows = [dict(r) for r in self.db.execute(sql, args).fetchall()]
        now = time.time()

        def count(key, fallback=None):
            d = {}
            for r in rows:
                value = r[key] or fallback
                if value:
                    d[value] = d.get(value, 0) + 1
            return d

        management = {}
        for r in rows:
            workshop = r["workshop"] or "Не назначен"
            shift = r["shift"] or UNASSIGNED_SHIFT
            key = (workshop, shift)
            group = management.setdefault(key, {
                "workshop": workshop, "shift": shift, "events": 0, "critical": 0, "pending": 0,
                "confirmed": 0, "false": 0, "forwarded": 0, "reactions": [], "types": {},
            })
            group["events"] += 1
            group["critical"] += r["severity"] == "critical"
            group["pending"] += r["status"] == "new"
            if r["status"] in ("confirmed", "false", "forwarded"):
                group[r["status"]] += 1
            if r["handled_ts"] is not None and r["status"] != "new":
                group["reactions"].append(r["handled_ts"] - r["ts"])
            group["types"][r["type"]] = group["types"].get(r["type"], 0) + 1
        management_rows = []
        for group in management.values():
            decided = group["confirmed"] + group["false"] + group["forwarded"]
            reactions = group.pop("reactions")
            types = group.pop("types")
            group["false_rate"] = group["false"] / decided if decided else None
            group["reaction_s_avg"] = sum(reactions) / len(reactions) if reactions else None
            group["top_type"] = max(types, key=types.get) if types else None
            management_rows.append(group)
        management_rows.sort(key=lambda group: (-group["events"], group["workshop"], group["shift"]))

        status = count("status")
        real = status.get("confirmed", 0) + status.get("forwarded", 0)
        decided = real + status.get("false", 0)
        delays = sorted(r["handled_ts"] - r["ts"] for r in rows if r["handled_ts"] and r["status"] != "new")
        pend = [r["ts"] for r in rows if r["status"] == "new"]
        pct = lambda p: delays[min(len(delays) - 1, int(len(delays) * p / 100))] if delays else None

        lo = float(since) if since else (min((r["ts"] for r in rows), default=now))
        hi = float(until) if until else now
        step = 3600 if hi - lo <= 3 * 86400 else 86400
        lo = (int(lo) // step) * step
        n = min(200, int((hi - lo) // step) + 1)
        lo = max(lo, (int(hi) // step - n + 1) * step)
        series = [{"t": lo + i * step, "counts": {}} for i in range(n)]
        for r in rows:
            i = int((r["ts"] - lo) // step)
            if 0 <= i < n:
                c = series[i]["counts"]
                c[r["type"]] = c.get(r["type"], 0) + 1
        heat = [[0] * 24 for _ in range(7)]
        for r in rows:
            lt = time.localtime(r["ts"])
            heat[lt.tm_wday][lt.tm_hour] += 1
        return {
            "total": len(rows), "critical": sum(1 for r in rows if r["severity"] == "critical"),
            "pending": status.get("new", 0), "oldest_pending_s": (now - min(pend)) if pend else None,
            "precision": (real / decided) if decided else None,
            "false_rate": (status.get("false", 0) / decided) if decided else None,
            "reaction_s": {"avg": sum(delays) / len(delays) if delays else None, "median": pct(50), "p90": pct(90),
                           "handled": len(delays)},
            "by_type": count("type"), "by_camera": count("camera"), "by_zone": count("zone"),
            "by_status": status, "by_severity": count("severity"),
            "by_workshop": count("workshop", "Не назначен"),
            "by_shift": count("shift", UNASSIGNED_SHIFT),
            "management": management_rows,
            "series": {"step_s": step, "buckets": series}, "heatmap": heat,
        }


class ZoneStore:
    """Зоны хранятся в нормированных координатах (0..1): не зависят от разрешения."""

    def __init__(self, path=None):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        data_dir = os.environ.get("LINQ_DATA", config.DATA_DIR)
        self.path = path or os.path.join(data_dir, "zones.json")
        self.lock = threading.Lock()
        try:
            with open(self.path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def get(self, cam):
        with self.lock:
            return list(self.data.get(cam, []))

    def set(self, cam, zones):
        clean = []
        for z in zones:
            pts = [[min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))] for x, y in z["points"]]
            if len(pts) >= 3:
                clean.append({"name": str(z.get("name") or "Зона")[:60], "points": pts})
        with self.lock:
            self.data[cam] = clean
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
        return clean

    def has(self, cam):
        return cam in self.data
