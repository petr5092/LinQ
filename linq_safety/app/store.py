"""Журнал событий (SQLite) и хранилище зон (JSON)."""
import json
import os
import sqlite3
import threading
import time

from . import config

STATUSES = ("new", "confirmed", "false", "forwarded")


class EventStore:
    def __init__(self, path=None):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        self.db = sqlite3.connect(path or os.path.join(config.DATA_DIR, "events.db"),
                                  check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, camera TEXT, type TEXT, label TEXT,
                severity TEXT, zone TEXT, track_id INTEGER, status TEXT, snapshot TEXT, latency_ms REAL)""")
            self.db.execute("CREATE INDEX IF NOT EXISTS ix_ts ON events(ts)")
            cols = {r[1] for r in self.db.execute("PRAGMA table_info(events)")}
            for col, typ in (("handled_ts", "REAL"), ("handled_by", "TEXT")):
                if col not in cols:
                    self.db.execute(f"ALTER TABLE events ADD COLUMN {col} {typ}")
            self.db.commit()

    def add(self, ev):
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO events(ts,camera,type,label,severity,zone,track_id,status,snapshot,latency_ms)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (ev["ts"], ev["camera"], ev["type"], ev["label"], ev["severity"], ev["zone"],
                 ev["track_id"], ev["status"], ev["snapshot"], ev["latency_ms"]))
            self.db.commit()
            return cur.lastrowid

    def query(self, type=None, camera=None, zone=None, status=None, since=None, until=None, limit=200):
        where, args = [], []
        for col, val in (("type", type), ("camera", camera), ("zone", zone), ("status", status)):
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
        with self.lock:
            self.db.execute("UPDATE events SET status=?, handled_ts=?, handled_by=? WHERE id=?",
                            (status, None if status == "new" else time.time(), by, eid))
            self.db.commit()
            r = self.db.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
        return dict(r) if r else None

    def get(self, eid):
        with self.lock:
            r = self.db.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
        return dict(r) if r else None

    def stats(self):
        with self.lock:
            rows = [dict(r) for r in self.db.execute("SELECT * FROM events").fetchall()]
        def count(key):
            d = {}
            for r in rows:
                if r[key]:
                    d[r[key]] = d.get(r[key], 0) + 1
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

        def count(key):
            d = {}
            for r in rows:
                if r[key]:
                    d[r[key]] = d.get(r[key], 0) + 1
            return d

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
            "series": {"step_s": step, "buckets": series}, "heatmap": heat,
        }


class ZoneStore:
    """Зоны хранятся в нормированных координатах (0..1): не зависят от разрешения."""

    def __init__(self, path=None):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        self.path = path or os.path.join(config.DATA_DIR, "zones.json")
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
