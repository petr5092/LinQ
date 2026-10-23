import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime

from app.enterprise import EnterpriseConfig
from app.hub import Hub
from app.logging_config import configure_logging, shutdown_logging
from app.server import serve
from app.store import EventStore, ZoneStore


def event(**values):
    return {
        "ts": time.time() - 30,
        "camera": "cam1",
        "type": "no_helmet",
        "label": "Нет каски",
        "severity": "medium",
        "zone": "Склад",
        "track_id": 1,
        "status": "new",
        "snapshot": "evidence.jpg",
        "latency_ms": 12.5,
        **values,
    }


class EnterpriseConfigTest(unittest.TestCase):
    def test_default_shift_boundaries(self):
        enterprise = EnterpriseConfig()

        def timestamp(hour, minute=0):
            return datetime(2026, 10, 23, hour, minute).timestamp()

        self.assertEqual(enterprise.shift_for(timestamp(7, 59)), ("Смена 1", "2026-10-23"))
        self.assertEqual(enterprise.shift_for(timestamp(8)), ("Смена 2", "2026-10-23"))
        self.assertEqual(enterprise.shift_for(timestamp(16)), ("Смена 3", "2026-10-23"))
        self.assertEqual(enterprise.shift_for(timestamp(23, 59)), ("Смена 3", "2026-10-23"))
        self.assertEqual(enterprise.shift_for(timestamp(0)), ("Смена 1", "2026-10-23"))

    def test_overnight_shift_is_attributed_to_start_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "enterprise.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"shifts": [
                    {"name": "Ночь", "start": "22:00", "end": "06:00"},
                    {"name": "Утро", "start": "06:00", "end": "14:00"},
                    {"name": "День", "start": "14:00", "end": "22:00"},
                ]}, f)
            enterprise = EnterpriseConfig(path)

        timestamp = datetime(2026, 10, 23, 2).timestamp()
        self.assertEqual(enterprise.shift_for(timestamp), ("Ночь", "2026-10-22"))

    def test_loads_camera_workshops_and_rejects_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "enterprise.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "shifts": [
                        {"name": "Ночь", "start": "00:00", "end": "08:00"},
                        {"name": "День", "start": "08:00", "end": "16:00"},
                        {"name": "Вечер", "start": "16:00", "end": "00:00"},
                    ],
                    "camera_workshops": {"cam1": "Сборочный цех"},
                }, f)
            enterprise = EnterpriseConfig(path)
            self.assertEqual(enterprise.workshop_for("cam1"), "Сборочный цех")
            self.assertEqual(enterprise.workshop_for("cam2"), "Не назначен")

            with open(path, "w", encoding="utf-8") as f:
                json.dump({"shifts": [{"name": "День", "start": "08:00", "end": "16:00"}]}, f)
            with self.assertRaisesRegex(ValueError, "покрывать все сутки"):
                EnterpriseConfig(path)


class EventAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = EventStore(os.path.join(self.temp.name, "events.db"))

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_status_changes_are_append_only_and_keep_actor(self):
        eid = self.store.add(event(workshop="Сборочный цех", shift="Смена 2", shift_date="2026-10-23"))

        self.assertEqual(self.store.set_status(eid, "confirmed", "Иван Иванов")["handled_by"], "Иван Иванов")
        self.store.set_status(eid, "confirmed", "Другой оператор")
        self.store.set_status(eid, "false", "Пётр Петров")
        self.store.set_status(eid, "new", "Иван Иванов")

        history = self.store.history(eid)
        self.assertEqual([(h["old_status"], h["new_status"], h["actor"]) for h in history], [
            ("new", "confirmed", "Иван Иванов"),
            ("confirmed", "false", "Пётр Петров"),
            ("false", "new", "Иван Иванов"),
        ])
        self.assertIsNone(self.store.get(eid)["handled_ts"])
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute("UPDATE event_history SET actor='изменено' WHERE id=?", (history[0]["id"],))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute("DELETE FROM event_history WHERE id=?", (history[0]["id"],))

    def test_invalid_and_missing_status_changes_do_not_write_audit(self):
        eid = self.store.add(event())

        self.assertIsNone(self.store.set_status(eid, "unknown", "Оператор"))
        self.assertIsNone(self.store.set_status(eid + 1, "confirmed", "Оператор"))
        self.assertEqual(self.store.history(eid), [])

    def test_dashboard_groups_enterprise_metrics(self):
        first = self.store.add(event(workshop="Цех A", shift="Смена 1", severity="critical"))
        self.store.set_status(first, "confirmed", "Оператор A")
        self.store.add(event(workshop="Цех A", shift="Смена 1", type="phone", severity="low"))
        self.store.add(event(workshop="Цех B", shift="Смена 3", status="new"))

        dashboard = self.store.dashboard(since=time.time() - 600)
        group = next(g for g in dashboard["management"] if g["workshop"] == "Цех A")
        self.assertEqual((group["shift"], group["events"], group["critical"]), ("Смена 1", 2, 1))
        self.assertEqual((group["confirmed"], group["pending"], group["top_type"]), (1, 1, "no_helmet"))
        self.assertIsNotNone(group["reaction_s_avg"])
        self.assertEqual(dashboard["by_workshop"], {"Цех A": 2, "Цех B": 1})

    def test_migrates_existing_event_database(self):
        path = os.path.join(self.temp.name, "old.db")
        old = sqlite3.connect(path)
        old.execute("""CREATE TABLE events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, camera TEXT, type TEXT, label TEXT,
            severity TEXT, zone TEXT, track_id INTEGER, status TEXT, snapshot TEXT, latency_ms REAL)""")
        old.execute(
            "INSERT INTO events(ts,camera,type,label,severity,zone,track_id,status,snapshot,latency_ms)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (time.time(), "cam1", "fall", "Падение", "critical", None, 4, "new", "old.jpg", 9.0))
        old.commit()
        old.close()

        migrated = EventStore(path)
        try:
            row = migrated.query()[0]
            self.assertIsNone(row["workshop"])
            self.assertIsNone(row["shift"])
            migrated.set_status(row["id"], "confirmed", "Оператор")
            self.assertEqual(migrated.history(row["id"])[0]["old_status"], "new")
        finally:
            migrated.db.close()

    def test_history_api_and_csv_include_attribution(self):
        eid = self.store.add(event(workshop="Участок A", shift="Смена 2", shift_date="2026-10-23"))
        self.store.set_status(eid, "confirmed", "Оператор API")
        server = serve(0, self.store, Hub(), ZoneStore(os.path.join(self.temp.name, "zones.json")),
                       [{"id": "cam1", "source": "private-source", "workshop": "Участок A"}],
                       type("Detector", (), {"name": "test", "last": {}})())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        log_path = os.path.join(self.temp.name, "linq.log")
        configure_logging(log_path)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urllib.request.urlopen(f"{base}/api/meta") as response:
                metadata = json.load(response)
            self.assertEqual(metadata["shifts"], ["Смена 1", "Смена 2", "Смена 3"])

            with urllib.request.urlopen(f"{base}/api/events/{eid}/history") as response:
                history = json.load(response)
            self.assertEqual(history[0]["actor"], "Оператор API")

            with urllib.request.urlopen(
                    f"{base}/api/events?workshop=%D0%A3%D1%87%D0%B0%D1%81%D1%82%D0%BE%D0%BA+A&shift=%D0%A1%D0%BC%D0%B5%D0%BD%D0%B0+2") as response:
                filtered = json.load(response)
            self.assertEqual([r["id"] for r in filtered], [eid])

            with urllib.request.urlopen(f"{base}/api/events.csv?private=query-must-not-be-logged") as response:
                csv_data = response.read().decode("utf-8-sig")
            self.assertIn("Участок A", csv_data)
            self.assertIn("Смена 2", csv_data)
            self.assertIn("Оператор API", csv_data)

            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(f"{base}/api/events/{eid + 10}/history")
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            shutdown_logging()
        with open(log_path, encoding="utf-8") as log_file:
            access_log = log_file.read()
        self.assertIn("path=/api/events.csv", access_log)
        self.assertNotIn("query-must-not-be-logged", access_log)




class DashboardTest(unittest.TestCase):
    def test_reaction_time_and_series(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            st = EventStore(os.path.join(temp_dir, "dashboard.db"))
            now = time.time()
            id_a = st.add(event(ts=now - 120))
            id_b = st.add(event(ts=now - 60, type="phone", severity="low"))
            st.add(event(ts=now - 10))
            st.set_status(id_a, "confirmed", "@m")
            st.set_status(id_b, "false", "@m")
            d = st.dashboard(since=now - 3600)
            self.assertEqual((d["total"], d["pending"]), (3, 1))
            self.assertEqual(d["precision"], 0.5)
            self.assertGreater(d["reaction_s"]["avg"], 50)
            self.assertEqual(sum(sum(b["counts"].values()) for b in d["series"]["buckets"]), 3)
            self.assertEqual(sum(map(sum, d["heatmap"])), 3)
            st.db.close()


if __name__ == "__main__":
    unittest.main()
