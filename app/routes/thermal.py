"""Radiometric temperature history and current heatmap endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import logging
import threading
import time
import uuid

import cv2
import numpy as np
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.db.models.camera import Camera
from app.db.models.thermal_reading import ThermalReading
from app.db.session import get_db
from app.schemas.incident import IncidentCreate
from app.services.incident_service import create_or_merge_incident
from app.services.notifications import notification_manager
from app.services.notifier import notifier
from app.storage.factory import get_storage_provider
from engine.thermal import ThermalAnalyzer

router = APIRouter(prefix="/thermal", tags=["Thermal monitoring"])
log = logging.getLogger(__name__)
_lock = threading.RLock()
_analyzers: dict[str, tuple[str, ThermalAnalyzer]] = {}
_last_history_write: dict[tuple[str, str], float] = {}
_latest: dict[str, dict] = {}
_last_cleanup = 0.0


class ThermalFramePayload(BaseModel):
    captured_at: datetime | None = None
    temperatures: list[list[float]] = Field(..., min_length=1, max_length=512)

    @field_validator("temperatures")
    @classmethod
    def validate_matrix(cls, rows: list[list[float]]) -> list[list[float]]:
        if not rows or len(rows) > 512:
            raise ValueError("Ожидается температурная матрица размером не более 640×512.")
        width = len(rows[0])
        if width < 1 or width > 640 or any(len(row) != width for row in rows):
            raise ValueError("Температурная матрица должна быть прямоугольной, шириной до 640 пикселей.")
        if len(rows) * width > 327680:
            raise ValueError("В кадре слишком много значений температуры.")
        return rows


def _camera_config(camera_id: str) -> dict:
    path = BASE_DIR / "configs" / "thermal_cameras.yaml"
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        camera_config = (config.get("cameras") or {}).get(camera_id)
    except (OSError, yaml.YAMLError) as exc:
        log.exception("Cannot read thermal camera configuration")
        raise HTTPException(503, "Не удалось прочитать настройки тепловизоров.") from exc
    if not isinstance(camera_config, dict) or not camera_config.get("zones"):
        raise HTTPException(409, f"Для камеры {camera_id} не настроены тепловые зоны.")
    return camera_config


def _analyzer(camera_id: str, camera_config: dict) -> ThermalAnalyzer:
    zones = camera_config["zones"]
    signature = repr(zones)
    current = _analyzers.get(camera_id)
    if current is None or current[0] != signature:
        try:
            analyzer = ThermalAnalyzer(zones)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(503, f"Некорректная конфигурация тепловых зон: {exc}") from exc
        _analyzers[camera_id] = (signature, analyzer)
        return analyzer
    return current[1]


def _render_heatmap(frame: np.ndarray, measurements: list[dict]) -> bytes:
    minimum = float(frame.min())
    maximum = float(frame.max())
    if maximum <= minimum:
        gray = np.zeros(frame.shape, dtype=np.uint8)
    else:
        gray = np.clip((frame - minimum) * (255.0 / (maximum - minimum)), 0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
    height, width = frame.shape
    for index, item in enumerate(measurements):
        x1, y1, x2, y2 = item["roi"]
        left, top = int(x1 * width), int(y1 * height)
        right, bottom = max(left + 1, int(x2 * width) - 1), max(top + 1, int(y2 * height) - 1)
        color = (20, 30, 255) if item["alarm"] else (230, 230, 230)
        cv2.rectangle(colored, (left, top), (right, bottom), color, 1)
        label = f"{item['zone_name']}: {item['max_temperature_c']:.1f} C"
        if item["alarm"]:
            cv2.putText(colored, label, (8, 22 + 22 * index), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (255, 255, 255), 2, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", colored, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        raise HTTPException(500, "Не удалось сформировать тепловую карту.")
    return encoded.tobytes()


_last_external_ingest_time: dict[str, float] = {}


def mark_external_ingest(camera_id: str) -> None:
    _last_external_ingest_time[camera_id] = time.monotonic()


def is_external_ingest_active(camera_id: str, threshold_seconds: float = 4.0) -> bool:
    return (time.monotonic() - _last_external_ingest_time.get(camera_id, 0.0)) < threshold_seconds


async def process_thermal_matrix(
    db: Session,
    camera_id: str,
    temperatures: Any,
    captured_at: datetime | None = None,
    is_external: bool = False,
) -> dict:
    """Evaluate a thermal frame against configured ROIs, update history, and trigger alerts on overheat."""
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(404, "Сначала зарегистрируйте камеру в системе.")
    if camera.camera_type != "thermal":
        raise HTTPException(409, "Камера должна быть зарегистрирована с типом thermal.")
    camera_config = _camera_config(camera_id)
    captured_at = captured_at or datetime.now().astimezone()
    captured_at_utc = captured_at.astimezone(timezone.utc).replace(tzinfo=None) if captured_at.tzinfo else captured_at
    captured_at_local = (
        captured_at.astimezone()
        if captured_at.tzinfo
        else captured_at.replace(tzinfo=timezone.utc).astimezone()
    )
    if is_external:
        mark_external_ingest(camera_id)

    try:
        frame = ThermalAnalyzer.validate_frame(temperatures)
        with _lock:
            measurements = _analyzer(camera_id, camera_config).process(frame)
            serializable = [measurement.as_dict() for measurement in measurements]
            heatmap = _render_heatmap(frame, serializable)
            _latest[camera_id] = {
                "camera_id": camera_id,
                "captured_at": captured_at.isoformat(),
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
                "minimum_temperature_c": round(float(frame.min()), 2),
                "maximum_temperature_c": round(float(frame.max()), 2),
                "measurements": serializable,
                "heatmap_jpeg_base64": base64.b64encode(heatmap).decode("ascii"),
            }
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        sample_interval = float(camera_config.get("sample_history_seconds", 5))
        retention_days = int(camera_config.get("retention_days", 90))
    except (TypeError, ValueError) as exc:
        raise HTTPException(503, "Некорректные интервалы истории тепловизора.") from exc
    if not np.isfinite(sample_interval) or sample_interval < 1 or not 1 <= retention_days <= 3650:
        raise HTTPException(503, "Интервал истории должен быть от 1 секунды, срок хранения — от 1 до 3650 дней.")
    now = time.monotonic()
    global _last_cleanup
    if now - _last_cleanup >= 3600:
        db.execute(delete(ThermalReading).where(
            ThermalReading.camera_id == camera_id,
            ThermalReading.captured_at < datetime.utcnow() - timedelta(days=retention_days)
        ))
        _last_cleanup = now
    for item in serializable:
        key = (camera_id, item["zone_id"])
        if item["alarm_started"] or (now - _last_history_write.get(key, 0.0) >= sample_interval):
            db.add(ThermalReading(
                camera_id=camera_id,
                zone_id=item["zone_id"],
                captured_at=captured_at_utc,
                min_temperature_c=item["min_temperature_c"],
                mean_temperature_c=item["mean_temperature_c"],
                max_temperature_c=item["max_temperature_c"],
                threshold_c=item["threshold_c"],
                hot_pixels=item["hot_pixels"],
                alarm=item["alarm"],
            ))
            _last_history_write[key] = now

        if not item["alarm_started"]:
            continue
        incident_id = f"TH-{uuid.uuid4().hex[:32]}"
        diff_c = round(float(item["max_temperature_c"]) - float(item["threshold_c"]), 1)
        description = (
            f"В зоне «{item['zone_name']}» зафиксирован перегрев: {item['max_temperature_c']:.1f} °C "
            f"при пороге {item['threshold_c']:.1f} °C (превышение: +{diff_c:.1f} °C). "
            f"Перегретых пикселей: {item['hot_pixels']}."
        )
        storage = get_storage_provider()
        image_key = storage.save_snapshot_key(heatmap, incident_id, camera_id)
        event = IncidentCreate(
            id=incident_id,
            site_id=camera.site_id,
            camera_id=camera.id,
            zone=item["zone_name"],
            title=f"Перегрев: {item['zone_name']} (+{diff_c:.1f} °C)",
            time=captured_at_local.strftime("%H:%M:%S"),
            severity=item["severity"],
            type="environment",
            description=description,
            action=item["action"],
            image_key=image_key,
        )
        incident, created = create_or_merge_incident(db, event, storage)
        data = incident.model_dump(mode="json")
        await notifier.broadcast({"event": "INCIDENT_CREATED" if created else "INCIDENT_UPDATED", "data": data})
        if created:
            notification_manager.dispatch_incident(data)
        else:
            notification_manager.refresh_incident(data)

    camera.online = True
    camera.last_heartbeat = datetime.utcnow()
    db.commit()
    return {key: value for key, value in _latest[camera_id].items() if key != "heatmap_jpeg_base64"}


@router.post("/cameras/{camera_id}/frame")
async def ingest_thermal_frame(
    camera_id: str,
    payload: ThermalFramePayload,
    db: Session = Depends(get_db),
):
    """Accept a Celsius matrix from a vendor SDK adapter and evaluate configured ROIs."""
    return await process_thermal_matrix(
        db=db,
        camera_id=camera_id,
        temperatures=payload.temperatures,
        captured_at=payload.captured_at,
        is_external=True,
    )


@router.get("/cameras/{camera_id}/latest")
def get_latest_thermal_frame(camera_id: str, db: Session = Depends(get_db)):
    if db.get(Camera, camera_id) is None:
        raise HTTPException(404, "Камера не найдена.")
    with _lock:
        latest = _latest.get(camera_id)
        if latest is None:
            raise HTTPException(404, "От тепловизора ещё не поступал радиометрический кадр.")
        return latest


@router.get("/cameras/{camera_id}/readings")
def get_thermal_readings(
    camera_id: str,
    zone_id: str | None = None,
    limit: int = Query(240, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    if db.get(Camera, camera_id) is None:
        raise HTTPException(404, "Камера не найдена.")
    query = select(ThermalReading).where(ThermalReading.camera_id == camera_id)
    if zone_id:
        query = query.where(ThermalReading.zone_id == zone_id)
    rows = db.scalars(query.order_by(ThermalReading.captured_at.desc()).limit(limit)).all()
    return [
        {
            "zone_id": row.zone_id,
            "captured_at": row.captured_at.isoformat(),
            "min_temperature_c": row.min_temperature_c,
            "mean_temperature_c": row.mean_temperature_c,
            "max_temperature_c": row.max_temperature_c,
            "threshold_c": row.threshold_c,
            "hot_pixels": row.hot_pixels,
            "alarm": row.alarm,
        }
        for row in reversed(rows)
    ]
