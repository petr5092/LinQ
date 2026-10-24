from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional
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
    Сводка по инцидентам и почасовая статистика за текущую дату сервера.
    При указании site_id все показатели ограничиваются выбранной площадкой.
    """
    incident_filters = [Incident.site_id == site_id] if site_id else []
    camera_filters = [Camera.site_id == site_id] if site_id else []

    def count_incidents(*filters: Any) -> int:
        return db.scalar(select(func.count(Incident.id)).where(*incident_filters, *filters)) or 0

    total_incidents = count_incidents()
    new_count = count_incidents(Incident.status == "new")
    working_count = count_incidents(Incident.status == "working")
    resolved_count = count_incidents(Incident.status == "resolved")
    dismissed_count = count_incidents(Incident.status == "dismissed")
    critical_count = count_incidents(Incident.severity == "critical")
    warning_count = count_incidents(Incident.severity == "warning")
    info_count = count_incidents(Incident.severity == "info")

    total_cameras = db.scalar(
        select(func.count(Camera.id)).where(*camera_filters)
    ) or 0
    online_cameras = db.scalar(
        select(func.count(Camera.id)).where(*camera_filters, Camera.online.is_(True))
    ) or 0

    today = date.today()
    today_start = datetime.combine(today, time.min)
    tomorrow_start = today_start + timedelta(days=1)
    today_incidents = db.execute(
        select(Incident.created_at, Incident.zone, Incident.type).where(
            *incident_filters,
            Incident.created_at >= today_start,
            Incident.created_at < tomorrow_start,
        )
    )
    hourly = [0] * 24
    zones: Counter[str] = Counter()
    types: Counter[str] = Counter()
    for created_at, zone, incident_type in today_incidents:
        hourly[created_at.hour] += 1
        zones[zone] += 1
        types[incident_type] += 1

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
                for name, count in zones.most_common()
            ],
            "by_type": [
                {"name": name, "count": count}
                for name, count in types.most_common()
            ],
        },
    }
