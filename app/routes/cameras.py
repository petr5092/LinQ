from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.camera import Camera
from app.db.models.site import Site
from app.schemas.camera import CameraRead, CameraCreate, CameraUpdate
from app.schemas.common import StatusResponse

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


@router.get("/{camera_id}", response_model=CameraRead)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    """Получение детальной информации о камере."""
    camera = db.scalar(select(Camera).where(Camera.id == camera_id))
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Камера не найдена")
    return camera


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
