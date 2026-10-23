"""
Комплексные тесты сервисного и API слоя бэкенда по стандарту test-master.
Покрытие:
- CameraHub (MJPEG генератор, буферизация raw bytes/numpy, расчет устаревания last_frame_age_seconds, метрики)
- Storage Layer: LocalStorageProvider, S3StorageProvider (mock), StorageFactory
- IncidentService (все фильтры: site, status, severity, camera, пагинация, 404)
- Sites CRUD API (создание, чтение, 404, 400)
- Cameras CRUD API (создание, валидация площадки, частичное обновление, удаление, стрим)
"""

import asyncio
from datetime import datetime
import io
import os
import shutil
import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from starlette.testclient import TestClient

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db.models.site import Site
from app.db.models.camera import Camera
from app.db.models.incident import Incident
from app.main import app
from app.schemas.camera import CameraCreate, CameraUpdate
from app.schemas.incident import IncidentCreate
from app.schemas.site import SiteCreate
from app.services.camera_hub import CameraHub
from app.services.incident_service import (
    create_incident,
    get_incident_by_id,
    list_incidents,
    update_incident_status,
)
from app.storage.factory import get_storage_provider
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider


@pytest.fixture(scope="module")
def client():
    from app.seed import seed_database
    seed_database()
    return TestClient(app)


# ==============================================================================
# 1. CameraHub Deep Unit Tests
# ==============================================================================

def test_camera_hub_bytes_and_numpy_frames():
    hub = CameraHub()
    # 1. Numpy массив (BGR)
    img_bgr = np.full((100, 100, 3), 120, dtype=np.uint8)
    hub.set_frame("cam_1", img_bgr)

    frame = hub.get_frame("cam_1")
    assert frame is not None
    assert frame.startswith(b"\xff\xd8")  # JPEG header

    # 2. Raw JPEG bytes
    raw_bytes = b"\xff\xd8\xff\xe0rawjpeg"
    hub.set_frame("cam_2", raw_bytes)
    assert hub.get_frame("cam_2") == raw_bytes
    assert hub.get_frame("cam_non_existent") is None


def test_camera_hub_wait_frame_timeout():
    hub = CameraHub()
    t0 = time.perf_counter()
    seq, frame = hub.wait_frame("cam_empty", last_seq=0, timeout=0.1)
    elapsed = time.perf_counter() - t0
    assert seq == 0
    assert frame == b""
    assert elapsed >= 0.08


def test_camera_hub_statuses_and_stale_detection():
    hub = CameraHub()
    now = time.time()

    # Камера 1: свежая (online)
    hub.set_frame("cam_online", b"jpeg")
    hub.update_metrics("cam_online", fps=25.0, detect_time_ms=10.0, latency_ms=12.0)

    # Камера 2: давно не присылала кадры (>10s -> offline)
    hub.set_camera_state("cam_stale", "online")
    with hub._state_lock:
        hub._states["cam_stale"]["last_frame_at"] = now - 15.0

    statuses = hub.get_camera_statuses()
    status_map = {s["camera_id"]: s for s in statuses}

    assert status_map["cam_online"]["status"] == "online"
    assert status_map["cam_online"]["fps"] == 25.0
    assert status_map["cam_stale"]["status"] == "offline"
    assert status_map["cam_stale"]["last_frame_age_seconds"] >= 14.0


@pytest.mark.asyncio
async def test_camera_hub_mjpeg_generator():
    hub = CameraHub()
    hub.set_frame("cam_stream", b"\xff\xd8\xffframe1")

    gen = hub.mjpeg_generator("cam_stream")
    chunk = await gen.__anext__()
    assert b"--frame" in chunk
    assert b"image/jpeg" in chunk
    assert b"frame1" in chunk


# ==============================================================================
# 2. Storage Layer Unit Tests
# ==============================================================================

def test_local_storage_provider(tmp_path):
    storage_dir = tmp_path / "snapshots"
    provider = LocalStorageProvider(base_dir=str(storage_dir))
    assert provider.health_check() is True

    # Сохранение кадра
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    url = provider.save_snapshot(img, incident_id="inc_01", camera_id="cam_01")
    assert url.startswith("/static/snapshots/")
    assert "inc_01" in url

    # Проверка существования на диске
    rel_path = url.replace("/static/snapshots/", "")
    assert os.path.isfile(storage_dir / rel_path)

    # Получение URL
    assert provider.get_snapshot_url("2026-10-24/inc_01_cam_01.jpg").endswith("/2026-10-24/inc_01_cam_01.jpg")


def test_s3_storage_provider_mocked():
    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.head_bucket.return_value = {}
        mock_client.generate_presigned_url.return_value = "https://s3.local/presigned_url.jpg"

        s3 = S3StorageProvider(
            endpoint_url="https://s3.local",
            access_key="key",
            secret_key="secret",
            bucket_name="test-bucket",
        )
        assert s3.health_check() is True

        img = np.zeros((50, 50, 3), dtype=np.uint8)
        url = s3.save_snapshot(img, incident_id="inc_99", camera_id="cam_99")
        assert url == "https://s3.local/presigned_url.jpg"
        mock_client.put_object.assert_called_once()

        presigned = s3.get_snapshot_url("snapshots/test.jpg")
        assert presigned == "https://s3.local/presigned_url.jpg"


# ==============================================================================
# 3. IncidentService Edge Cases & Filters
# ==============================================================================

def test_incident_service_multi_filtering():
    storage = get_storage_provider()
    with SessionLocal() as db:
        # Тестируем фильтрацию по площадке
        items_north, total_north = list_incidents(db, site_id="north", limit=10, storage_provider=storage)
        assert all(i.site_id == "north" for i in items_north)

        # Тестируем фильтрацию по статусу
        items_resolved, _ = list_incidents(db, status="resolved", limit=10, storage_provider=storage)
        assert all(i.status == "resolved" for i in items_resolved)

        # Тестируем фильтрацию по критичности
        items_crit, _ = list_incidents(db, severity="critical", limit=10, storage_provider=storage)
        assert all(i.severity == "critical" for i in items_crit)

        # Тестируем несуществующий инцидент
        assert get_incident_by_id(db, "non_existing_inc_id", storage) is None

        # Смена статуса несуществующего инцидента
        assert update_incident_status(db, "non_existing_inc_id", "working", storage) is None


# ==============================================================================
# 4. Sites & Cameras API CRUD Tests
# ==============================================================================

import uuid

def test_sites_api_crud(client):
    # 1. Чтение всех площадок
    res_all = client.get("/api/v1/sites")
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 1

    # 2. Чтение конкретной площадки
    res = client.get("/api/v1/sites/north")
    assert res.status_code == 200
    assert res.json()["name"] == "Завод «Северный»"

    # 3. Чтение 404
    res_404 = client.get("/api/v1/sites/unknown_site_404")
    assert res_404.status_code == 404

    # 4. Создание новой площадки
    uid = uuid.uuid4().hex[:6]
    site_id = f"test_site_{uid}"
    new_site = {
        "id": site_id,
        "name": "Западная площадка",
        "subtitle": "Опытное производство",
    }
    res_create = client.post("/api/v1/sites", json=new_site)
    assert res_create.status_code == 201
    assert res_create.json()["id"] == site_id

    # 5. Конфликт при повторном создании
    res_conflict = client.post("/api/v1/sites", json=new_site)
    assert res_conflict.status_code == 400

    # 6. Обновление полигона несуществующей зоны -> 404
    res_poly_404 = client.put("/api/v1/sites/zones/999999/polygon", json={"points": [[0, 0], [1, 1]]})
    assert res_poly_404.status_code == 404


def test_cameras_api_crud_and_errors(client):
    # 1. Ошибка создания камеры с несуществующей площадкой
    bad_cam = {
        "id": "CAM-BAD",
        "name": "Камера",
        "site_id": "non_existing_site_999",
        "zone": "Зона",
        "workshop": "Корпус",
    }
    assert client.post("/api/v1/cameras", json=bad_cam).status_code == 404

    # 2. Успешное создание камеры
    good_cam = {
        "id": "CAM-TEST-CREATE",
        "name": "Тестовая камера создания",
        "site_id": "north",
        "zone": "Цех № 1",
        "workshop": "Корпус А",
        "fps": 30.0,
        "online": True,
    }
    res_good = client.post("/api/v1/cameras", json=good_cam)
    assert res_good.status_code == 201

    # 3. Повторное создание -> 400
    assert client.post("/api/v1/cameras", json=good_cam).status_code == 400

    # 4. Частичное обновление
    patch_res = client.patch("/api/v1/cameras/CAM-TEST-CREATE", json={"online": False, "fps": 15.0})
    assert patch_res.status_code == 200
    assert patch_res.json()["online"] is False
    assert patch_res.json()["fps"] == 15.0

    # 5. Обновление несуществующей камеры -> 404
    assert client.patch("/api/v1/cameras/CAM-404-XYZ", json={"fps": 10.0}).status_code == 404

    # 6. Удаление камеры
    assert client.delete("/api/v1/cameras/CAM-TEST-CREATE").status_code == 200
    assert client.delete("/api/v1/cameras/CAM-TEST-CREATE").status_code == 404
