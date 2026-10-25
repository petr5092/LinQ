import numpy as np
import pytest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.camera import Camera
from app.db.models.site import Site
from app.services.browser_camera import _handle_browser_incident
from app.services.camera_hub import camera_hub
from engine.deduplication.types import ConfirmedIncident, IncidentState
from engine.inference.base import BoundingBox
from engine.rules.base import ViolationSeverity


def test_browser_camera_incident_dispatches_notification(tmp_path, monkeypatch):
    # Set up in-memory DB
    database = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(database)
    sessions = sessionmaker(bind=database)

    with sessions() as db:
        db.add(Site(id='north', name='North Site'))
        db.flush()
        db.add(Camera(id='BROWSER-CAM-01', site_id='north', name='Webcam Test', zone='Цех № 1', workshop='Корпус А'))
        db.commit()

    monkeypatch.setattr('app.services.browser_camera.SessionLocal', sessions)

    from app.storage.local import LocalStorageProvider
    storage = LocalStorageProvider(str(tmp_path / 'snapshots'))
    monkeypatch.setattr('app.services.browser_camera.get_storage_provider', lambda: storage)

    mock_dispatch = Mock()
    monkeypatch.setattr('app.services.browser_camera.notification_manager.dispatch_incident', mock_dispatch)

    mock_broadcast = Mock()
    monkeypatch.setattr('app.services.browser_camera.notifier.broadcast_sync', mock_broadcast)

    mock_sink = Mock()

    # Create dummy violation frame and confirmed incident
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    incident = ConfirmedIncident(
        rule_name="ppe_compliance",
        rule_id="PPE_NO_HELMET_1",
        severity=ViolationSeverity.HIGH,
        camera_id="BROWSER-CAM-01",
        track_id=1,
        involved_track_ids=[1],
        description="Нарушение правил ТБ: у сотрудника #1 отсутствует защитная каска",
        bbox=BoundingBox(100, 100, 200, 300),
        zone_id="Цех № 1",
        first_seen_at=100.0,
        confirmed_at=101.0,
        last_seen_at=101.0,
        duration_seconds=1.0,
        state=IncidentState.CONFIRMED,
        metadata={"ppe_type": "helmet"},
    )

    camera_info = {
        "camera_id": "BROWSER-CAM-01",
        "site_id": "north",
        "zone": "Цех № 1",
    }

    _handle_browser_incident(incident, frame, camera_info, mock_sink)

    # 1. Verify CameraHub received violation frame
    violation_frame = camera_hub.get_violation_frame("BROWSER-CAM-01")
    assert violation_frame is not None

    # 2. Verify WebSocket broadcast was invoked
    assert mock_broadcast.called
    broadcast_call = mock_broadcast.call_args[0][0]
    assert broadcast_call["event"] == "INCIDENT_CREATED"
    assert broadcast_call["data"]["camera_id"] == "BROWSER-CAM-01"

    # 3. Verify notification_manager.dispatch_incident was called
    assert mock_dispatch.called
    dispatched_data, dispatched_snap = mock_dispatch.call_args[0]
    assert dispatched_data["camera_id"] == "BROWSER-CAM-01"
    assert dispatched_data["title"] == "Сотрудник без каски"
    assert dispatched_snap.startswith("/static/snapshots/")
