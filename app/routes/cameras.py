import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.camera import Camera
from app.db.models.incident import Incident
from app.db.models.site import Site
from app.schemas.camera import CameraRead, CameraCreate, CameraUpdate
from app.schemas.common import StatusResponse
from app.services.camera_hub import camera_hub
from app.storage.factory import get_storage_provider

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", response_model=List[CameraRead])
def list_cameras(
    site_id: Optional[str] = None,
    online: Optional[bool] = None,
    zone: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Список видеокамер с фильтрацией по площадке, зоне и статусу online."""
    stmt = select(Camera)
    if site_id:
        stmt = stmt.where(Camera.site_id == site_id)
    if online is not None:
        stmt = stmt.where(Camera.online == online)
    if zone:
        stmt = stmt.where(Camera.zone == zone)

    cameras = db.scalars(stmt.order_by(Camera.id)).all()
    return cameras


@router.get("/statuses/live")
def get_live_camera_statuses():
    """Оперативные статусы всех активных камер из CameraHub (онлайн, офлайн, FPS, задержка)."""
    return camera_hub.get_camera_statuses()


@router.get("/{camera_id}", response_model=CameraRead)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    """Получение детальной информации о камере."""
    camera = db.scalar(select(Camera).where(Camera.id == camera_id))
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Камера не найдена")
    return camera


@router.get("/{camera_id}/stream")
@router.get("/{camera_id}/stream.mjpg")
async def stream_camera(camera_id: str):
    """Прямой MJPEG-видеопоток с камеры (multipart/x-mixed-replace)."""
    return StreamingResponse(
        camera_hub.mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/{camera_id}/frame.jpg")
def get_camera_frame(camera_id: str, mode: Optional[str] = None):
    """Получение последнего JPEG-кадра с камеры (если mode='snapshot' или 'violation', возвращает кадр последнего нарушения)."""
    if mode in ("snapshot", "violation"):
        frame_bytes = camera_hub.get_snapshot(camera_id)
    else:
        frame_bytes = camera_hub.get_frame(camera_id) or camera_hub.get_snapshot(camera_id)
    if not frame_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Свежий кадр для камеры '{camera_id}' пока не получен",
        )
    return Response(
        content=frame_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/{camera_id}/snapshot.jpg")
def get_camera_snapshot(camera_id: str, db: Session = Depends(get_db)):
    """Получение стоп-кадра последнего зафиксированного нарушения с камеры."""
    frame_bytes = camera_hub.get_violation_frame(camera_id)
    if not frame_bytes:
        incident = db.scalar(
            select(Incident)
            .where(Incident.camera_id == camera_id, Incident.image_key != "")
            .order_by(desc(Incident.created_at))
            .limit(1)
        )
        if incident and incident.image_key:
            storage = get_storage_provider()
            if hasattr(storage, "base_dir"):
                img_path = os.path.join(storage.base_dir, incident.image_key.lstrip("/"))
                if os.path.isfile(img_path):
                    try:
                        with open(img_path, "rb") as f:
                            frame_bytes = f.read()
                    except OSError:
                        pass
    if not frame_bytes:
        frame_bytes = camera_hub.get_frame(camera_id)
    if not frame_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Стоп-кадр для камеры '{camera_id}' пока не получен",
        )
    return Response(
        content=frame_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/{camera_id}/metrics")
def get_camera_metrics(camera_id: str):
    """Показатели производительности камеры (FPS, latency, detect_time_ms)."""
    return camera_hub.get_metrics(camera_id)


@router.post("", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def create_camera(camera_in: CameraCreate, db: Session = Depends(get_db)):
    """Регистрация новой камеры наблюдения."""
    existing = db.scalar(select(Camera).where(Camera.id == camera_in.id))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Камера с ID '{camera_in.id}' уже зарегистрирована",
        )

    # Проверяем наличие площадки
    site = db.scalar(select(Site).where(Site.id == camera_in.site_id))
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Площадка '{camera_in.site_id}' не найдена",
        )

    camera = Camera(
        id=camera_in.id,
        name=camera_in.name,
        zone=camera_in.zone,
        workshop=camera_in.workshop,
        site_id=camera_in.site_id,
        rtsp_url=camera_in.rtsp_url,
        camera_type=camera_in.camera_type,
        image_placeholder=camera_in.image_placeholder,
        online=camera_in.online,
        fps=camera_in.fps,
        last_heartbeat=datetime.utcnow(),
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(camera_id: str, camera_update: CameraUpdate, db: Session = Depends(get_db)):
    """Частичное обновление данных камеры (включение/отключение, RTSP URL и т.д.)."""
    camera = db.scalar(select(Camera).where(Camera.id == camera_id))
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Камера не найдена")

    update_data = camera_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(camera, field, value)

    camera.last_heartbeat = datetime.utcnow()
    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/{camera_id}", response_model=StatusResponse)
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    """Удаление камеры."""
    camera = db.scalar(select(Camera).where(Camera.id == camera_id))
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Камера не найдена")

    db.delete(camera)
    db.commit()
    return StatusResponse(message=f"Камера {camera_id} удалена")
