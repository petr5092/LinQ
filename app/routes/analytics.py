from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.incident import Incident
from app.db.models.camera import Camera

router = APIRouter(prefix="/analytics", tags=["Analytics & Dashboard"])


@router.get("/summary")
def get_analytics_summary(site_id: Optional[str] = None, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Сводка по инцидентам и почасовая статистика за текущую дату сервера.
    При указании site_id все показатели ограничиваются выбранной площадкой.
    """
    incident_filters = [Incident.site_id == site_id] if site_id else []
    camera_filters = [Camera.site_id == site_id] if site_id else []

    incident_counts = db.execute(
        select(
            func.count(Incident.id),
            func.count(Incident.id).filter(Incident.status == "new"),
            func.count(Incident.id).filter(Incident.status == "working"),
            func.count(Incident.id).filter(Incident.status == "resolved"),
            func.count(Incident.id).filter(Incident.status == "dismissed"),
            func.count(Incident.id).filter(Incident.severity == "critical"),
            func.count(Incident.id).filter(Incident.severity == "warning"),
            func.count(Incident.id).filter(Incident.severity == "info"),
        ).where(*incident_filters)
    ).one()
    (
        total_incidents,
        new_count,
        working_count,
        resolved_count,
        dismissed_count,
        critical_count,
        warning_count,
        info_count,
    ) = incident_counts

    total_cameras = db.scalar(
        select(func.count(Camera.id)).where(*camera_filters)
    ) or 0
    online_cameras = db.scalar(
        select(func.count(Camera.id)).where(*camera_filters, Camera.online.is_(True))
    ) or 0

    today = date.today()
    today_start = datetime.combine(today, time.min)
    tomorrow_start = today_start + timedelta(days=1)
    today_filters = [
        *incident_filters,
        Incident.created_at >= today_start,
        Incident.created_at < tomorrow_start,
    ]
    if db.get_bind().dialect.name == "sqlite":
        hour_expression = cast(func.strftime("%H", Incident.created_at), Integer)
    else:
        hour_expression = func.extract("hour", Incident.created_at)

    hourly = [0] * 24
    for hour, count in db.execute(
        select(hour_expression, func.count(Incident.id))
        .where(*today_filters)
        .group_by(hour_expression)
    ):
        hourly[int(hour)] = count

    zones = db.execute(
        select(Incident.zone, func.count(Incident.id))
        .where(*today_filters)
        .group_by(Incident.zone)
        .order_by(func.count(Incident.id).desc())
    ).all()
    types = db.execute(
        select(Incident.type, func.count(Incident.id))
        .where(*today_filters)
        .group_by(Incident.type)
        .order_by(func.count(Incident.id).desc())
    ).all()

    return {
        "date": today.isoformat(),
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
            "info": info_count,
        },
        "cameras": {
            "total": total_cameras,
            "online": online_cameras,
            "offline": total_cameras - online_cameras,
        },
        "today": {
            "total": sum(hourly),
            "hourly": hourly,
            "by_zone": [
                {"name": name, "count": count}
                for name, count in zones
            ],
            "by_type": [
                {"name": name, "count": count}
                for name, count in types
            ],
        },
    }
