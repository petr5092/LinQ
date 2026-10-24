import base64
import json
import threading
from unittest.mock import Mock, AsyncMock
import uuid

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.models.site import Site
from app.db.models.camera import Camera
from app.db.models.incident import Incident
from app.routes import worker
from app.storage.local import LocalStorageProvider
from engine.config import build_rules, load_config, inference_options
from engine.deduplication.types import ConfirmedIncident
from engine.inference.base import BoundingBox
from engine.incident_client import IncidentClient, incident_payload
from run_worker import run_camera_worker


@pytest.fixture
def cv_api(tmp_path, monkeypatch):
    database = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(database)
    sessions = sessionmaker(bind=database)
    with sessions() as db:
        db.add(Site(id='north', name='Test site'))
        db.flush()
        db.add(Camera(id='CAM-01', site_id='north', name='Test camera', zone='gate', workshop='test'))
        db.commit()
    def session():
        with sessions() as db:
            yield db
    storage = LocalStorageProvider(str(tmp_path / 'snapshots'))
    broadcast = AsyncMock()
    dispatch = Mock()
    refresh = Mock()
    app.dependency_overrides[get_db] = session
    monkeypatch.setattr(worker, 'get_storage_provider', lambda: storage)
    monkeypatch.setattr(worker.notifier, 'broadcast', broadcast)
    monkeypatch.setattr(worker.notification_manager, 'dispatch_incident', dispatch)
    monkeypatch.setattr(worker.notification_manager, 'refresh_incident', refresh)
    try:
        yield TestClient(app), sessions, storage, broadcast, dispatch, refresh
    finally:
        app.dependency_overrides.pop(get_db, None)
        database.dispose()


def envelope():
    frame = np.zeros((100, 200, 3), np.uint8)
    event = ConfirmedIncident(rule_name='danger_zone', bbox=BoundingBox(20, 10, 60, 50),
                              confirmed_at=1792800000, description='Danger zone', track_id=4)
    payload = incident_payload(event, frame, {'camera_id': 'CAM-01', 'site_id': 'north'})
    ok, jpeg = cv2.imencode('.jpg', frame)
    assert ok
    return {'incident': payload, 'jpeg_base64': base64.b64encode(jpeg).decode()}


def test_cv_api_persists_once_and_stores_key_not_base64(cv_api):
    client, sessions, storage, broadcast, dispatch, _ = cv_api
    data = envelope()
    first = client.post('/api/v1/worker/incidents', json=data)
    second = client.post('/api/v1/worker/incidents', json=data)
    assert first.status_code == 201
    assert second.status_code == 200
    body = first.json()
    assert body['box'] == [10, 10, 20, 40]
    assert body['snapshot_url'].count('/static/snapshots/') == 1
    assert not body['image_key'].startswith('/')
    assert body['image_key'].endswith('.jpg')
    assert (storage.base_dir and body['image_key'])
    with sessions() as db:
        assert db.scalar(select(func.count(Incident.id))) == 1
    broadcast.assert_awaited_once()
    assert broadcast.await_args.args[0]['event'] == 'INCIDENT_CREATED'
    dispatch.assert_called_once()


def test_cv_worker_merges_repeated_incidents_and_refreshes_notifications(cv_api):
    client, sessions, _, broadcast, dispatch, refresh = cv_api
    first = client.post('/api/v1/worker/incidents', json=envelope())
    second = client.post('/api/v1/worker/incidents', json=envelope())

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()['id'] == first.json()['id']
    with sessions() as db:
        assert db.scalar(select(func.count(Incident.id))) == 1

    assert [call.args[0]['event'] for call in broadcast.await_args_list] == [
        'INCIDENT_CREATED',
        'INCIDENT_UPDATED',
    ]
    dispatch.assert_called_once()
    refresh.assert_called_once()


@pytest.mark.parametrize('field,value', [('camera_id', 'unknown'), ('site_id', 'wrong'), ('id', '../escape')])
def test_cv_api_rejects_wrong_camera_or_unsafe_id(cv_api, field, value):
    data = envelope()
    data['incident'][field] = value
    assert cv_api[0].post('/api/v1/worker/incidents', json=data).status_code == 422


def test_cv_api_rejects_bad_jpeg(cv_api):
    data = envelope()
    data['jpeg_base64'] = '!!!!'
    assert cv_api[0].post('/api/v1/worker/incidents', json=data).status_code == 422


def test_browser_camera_requires_registered_camera_and_jpeg(cv_api):
    client = cv_api[0]
    assert client.post(
        '/api/v1/worker/browser-frame/unknown',
        content=b'frame',
        headers={'Content-Type': 'image/jpeg'},
    ).status_code == 404
    assert client.post(
        '/api/v1/worker/browser-frame/CAM-01',
        content=b'frame',
        headers={'Content-Type': 'image/png'},
    ).status_code == 415


def test_browser_camera_frame_returns_detection_payload(cv_api, monkeypatch):
    from app.routes import worker

    expected = {
        'camera_id': 'CAM-01',
        'width': 100,
        'height': 80,
        'detections': [],
        'violations': [],
        'new_incidents': [],
        'metrics': {'backend': 'ONNX_CPU', 'inference_ms': 12.0, 'fps': 4.0},
    }
    monkeypatch.setattr(worker, 'process_browser_frame', lambda _camera, _jpeg: expected)
    frame = np.zeros((80, 100, 3), np.uint8)
    ok, jpeg = cv2.imencode('.jpg', frame)
    assert ok
    response = cv_api[0].post(
        '/api/v1/worker/browser-frame/CAM-01',
        content=jpeg.tobytes(),
        headers={'Content-Type': 'image/jpeg'},
    )
    assert response.status_code == 200
    assert response.json() == expected


def test_browser_camera_configuration_error_is_returned_to_client(cv_api, monkeypatch):
    from app.routes import worker

    monkeypatch.setattr(
        worker,
        'process_browser_frame',
        Mock(side_effect=worker.BrowserCameraConfigurationError('ONNX model is unavailable')),
    )
    frame = np.zeros((80, 100, 3), np.uint8)
    ok, jpeg = cv2.imencode('.jpg', frame)
    assert ok
    response = cv_api[0].post(
        '/api/v1/worker/browser-frame/CAM-01',
        content=jpeg.tobytes(),
        headers={'Content-Type': 'image/jpeg'},
    )
    assert response.status_code == 409
    assert response.json()['detail'] == 'ONNX model is unavailable'


def test_outbox_retains_failure_and_removes_only_after_success(tmp_path, monkeypatch):
    from engine import incident_client
    sink = IncidentClient('http://example.invalid/api/v1', tmp_path)
    frame = np.zeros((100, 200, 3), np.uint8)
    sink.submit(ConfirmedIncident(confirmed_at=1792800000), frame, {'camera_id': 'CAM-01', 'site_id': 'north'})
    monkeypatch.setattr(incident_client, 'urlopen', Mock(side_effect=OSError('offline')))
    sink.flush()
    files = list(tmp_path.glob('*.json'))
    assert len(files) == 1
    event_id = json.loads(files[0].read_text(encoding='utf-8'))['incident']['id']
    assert str(uuid.UUID(event_id)) == event_id
    from unittest.mock import MagicMock
    monkeypatch.setattr(incident_client, 'urlopen', MagicMock())
    sink.flush()
    assert not list(tmp_path.glob('*.json'))


def test_ppe_cannot_run_on_person_only_model():
    with pytest.raises(ValueError, match='PPE'):
        build_rules({'rules': {'ppe_compliance': {'enabled': True}}}, {}, {0: 'person'})


def test_phone_class_from_coco_is_used():
    rules = build_rules({'rules': {'phone_usage': {'enabled': True}}}, {}, {0: 'person', 1: 'cell phone'})
    assert rules.get_rule('phone_usage').phone_class_name == 'cell phone'


def test_configured_worker_rules_use_shared_registry():
    config = load_config()
    camera = config['cameras'][0]
    class_names = {
        0: 'person',
        1: 'helmet',
        2: 'vest',
        3: 'forklift',
    }

    rules = build_rules(config, camera, class_names)

    assert set(rules.rules) == {
        'danger_zone',
        'proximity',
        'fall_detection',
        'ppe_compliance',
    }
    assert rules.get_rule('proximity').safe_distance_px == 140.0


def test_worker_configuration_smoke(tmp_path):
    config = load_config()
    options = inference_options(config, 'mock')
    camera = {**config['cameras'][0], 'source': 'synthetic'}
    count = run_camera_worker(camera, config, options, threading.Event(), IncidentClient(None, tmp_path),
                              max_frames=3, realtime=False)
    assert count == 3
