from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.incident import Incident
from app.db.models.camera import Camera

router = APIRouter(prefix="/analytics", tags=["Analytics & Dashboard"])


@router.get("/summary")
def get_analytics_summary(site_id: Optional[str] = None, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Аналитическая сводка нарушений:
    - Общее количество зафиксированных событий
    - Активные инциденты (новые + в работе)
    - Устраненные нарушения
    - Распределение по степени критичности (critical, warning, info)
    - Статистика по камерам (online / total)
    """
    inc_query = select(Incident)
    cam_query = select(Camera)
    if site_id:
        inc_query = inc_query.where(Incident.site_id == site_id)
        cam_query = cam_query.where(Camera.site_id == site_id)

    # Статусы
    total_incidents = db.scalar(
        select(func.count(Incident.id)).where(Incident.site_id == site_id) if site_id
        else select(func.count(Incident.id))
    ) or 0

    new_count = db.scalar(
        select(func.count(Incident.id)).where(Incident.status == "new")
    ) or 0

    working_count = db.scalar(
        select(func.count(Incident.id)).where(Incident.status == "working")
    ) or 0

    resolved_count = db.scalar(
        select(func.count(Incident.id)).where(Incident.status == "resolved")
    ) or 0

    dismissed_count = db.scalar(
        select(func.count(Incident.id)).where(Incident.status == "dismissed")
    ) or 0

    # Критичность
    critical_count = db.scalar(
        select(func.count(Incident.id)).where(Incident.severity == "critical")
    ) or 0

    warning_count = db.scalar(
        select(func.count(Incident.id)).where(Incident.severity == "warning")
    ) or 0

    # Камеры
    total_cameras = db.scalar(select(func.count(Camera.id))) or 0
    online_cameras = db.scalar(select(func.count(Camera.id)).where(Camera.online.is_(True))) or 0

    return {
        "incidents": {
            "total": total_incidents,
            "active": new_count + working_count,
            "new": new_count,
            "working": working_count,
            "resolved": resolved_count,
            "dismissed": dismissed_count,
        },
        "severity": {
            "critical": critical_count,
            "warning": warning_count,
        },
        "cameras": {
            "total": total_cameras,
            "online": online_cameras,
            "offline": total_cameras - online_cameras,
        }
    }
