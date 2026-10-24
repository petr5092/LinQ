import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.camera import Camera
from app.db.models.incident import Incident
from app.db.models.site import Site
from app.routes.analytics import get_analytics_summary


class TestAnalyticsSummary(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        self.db.add_all([
            Site(id="north", name="Северная площадка"),
            Site(id="south", name="Южная площадка"),
            Camera(
                id="north-online",
                name="Камера 1",
                zone="Цех 1",
                workshop="Корпус А",
                site_id="north",
                online=True,
            ),
            Camera(
                id="north-offline",
                name="Камера 2",
                zone="Цех 2",
                workshop="Корпус А",
                site_id="north",
                online=False,
            ),
            Camera(
                id="south-online",
                name="Камера 3",
                zone="Цех 3",
                workshop="Корпус Б",
                site_id="south",
                online=True,
            ),
        ])
        now = datetime.now()
        self.db.add_all([
            Incident(
                id="north-today",
                site_id="north",
                camera_id="north-online",
                zone="Цех 1",
                title="Нарушение СИЗ",
                time=now.strftime("%H:%M:%S"),
                severity="critical",
                type="person",
                status="new",
                created_at=now,
            ),
            Incident(
                id="north-yesterday",
                site_id="north",
                camera_id="north-offline",
                zone="Цех 2",
                title="Предмет в проходе",
                time="10:00:00",
                severity="warning",
                type="environment",
                status="resolved",
                created_at=now - timedelta(days=1),
            ),
            Incident(
                id="south-today",
                site_id="south",
                camera_id="south-online",
                zone="Цех 3",
                title="Нарушение доступа",
                time=now.strftime("%H:%M:%S"),
                severity="critical",
                type="access",
                status="working",
                created_at=now,
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_site_filter_applies_to_every_summary_and_daily_chart(self):
        summary = get_analytics_summary(site_id="north", db=self.db)

        self.assertEqual(summary["incidents"]["total"], 2)
        self.assertEqual(summary["incidents"]["active"], 1)
        self.assertEqual(summary["incidents"]["resolved"], 1)
        self.assertEqual(summary["severity"], {"critical": 1, "warning": 1, "info": 0})
        self.assertEqual(summary["cameras"], {"total": 2, "online": 1, "offline": 1})
        self.assertEqual(summary["today"]["total"], 1)
        self.assertEqual(sum(summary["today"]["hourly"]), 1)
        self.assertEqual(summary["today"]["by_zone"], [{"name": "Цех 1", "count": 1}])
        self.assertEqual(summary["today"]["by_type"], [{"name": "person", "count": 1}])

    def test_unfiltered_summary_includes_all_sites_and_daily_incidents(self):
        summary = get_analytics_summary(db=self.db)

        self.assertEqual(summary["incidents"]["total"], 3)
        self.assertEqual(summary["incidents"]["active"], 2)
        self.assertEqual(summary["severity"]["critical"], 2)
        self.assertEqual(summary["cameras"], {"total": 3, "online": 2, "offline": 1})
        self.assertEqual(summary["today"]["total"], 2)


if __name__ == "__main__":
    unittest.main()
