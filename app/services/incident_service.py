import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.db.models.incident import Incident
from app.db.models.camera import Camera
from app.schemas.incident import (
    IncidentCreate,
    IncidentRead,
    EmployeeInfo,
    ContactInfo
)
from app.storage.base import BaseStorageProvider

INCIDENT_MERGE_WINDOW_SECONDS = 300


def map_incident_to_read(incident: Incident, storage_provider: Optional[BaseStorageProvider] = None) -> IncidentRead:
    """Преобразование ORM-модели инцидента в схему IncidentRead с URL снапшота."""
    snapshot_url = None
    placeholders = {'construction', 'workshop', 'warehouse', 'gate', 'perimeter'}
    if incident.image_key:
        if incident.image_key in placeholders:
            snapshot_url = f'/images/{incident.image_key}.png'
        elif incident.image_key.startswith('/') or incident.image_key.startswith('http'):
            snapshot_url = incident.image_key
        elif storage_provider:
            snapshot_url = storage_provider.get_snapshot_url(incident.image_key)
        else:
            snapshot_url = incident.image_key

    video_url = None
    if getattr(incident, 'camera', None) and incident.camera.rtsp_url:
        video_url = incident.camera.rtsp_url
    elif incident.camera_id == 'CAM-01':
        video_url = '/videos/construction_safety.mp4' 

    employee = None
    if incident.employee_name:
        employee = EmployeeInfo(
            name=incident.employee_name or "",
            role=incident.employee_role or "",
            number=incident.employee_number or "",
            access=incident.employee_access or "",
        )

    contact = None
    if incident.contact_name:
        contact = ContactInfo(
            name=incident.contact_name or "",
            role=incident.contact_role or "",
            radio=incident.contact_radio or "",
            phone=incident.contact_phone or "",
        )

    return IncidentRead(
        id=incident.id,
        site_id=incident.site_id,
        camera_id=incident.camera_id,
        zone=incident.zone,
        title=incident.title,
        time=incident.time,
        severity=incident.severity,
        type=incident.type,
        description=incident.description,
        action=incident.action,
        image_key=incident.image_key,
        snapshot_url=snapshot_url,
        video_url=video_url,
        status=incident.status,
        box=incident.box,
        employee_name=incident.employee_name,
        employee_role=incident.employee_role,
        employee_number=incident.employee_number,
        employee_access=incident.employee_access,
        contact_name=incident.contact_name,
        contact_role=incident.contact_role,
        contact_radio=incident.contact_radio,
        contact_phone=incident.contact_phone,
        track_id=incident.track_id,
        confidence=incident.confidence,
        is_verified=incident.is_verified,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        employee=employee,
        contact=contact,
    )


def list_incidents(
    db: Session,
    site_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    camera_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    storage_provider: Optional[BaseStorageProvider] = None,
) -> Tuple[List[IncidentRead], int]:
    """Получение списка инцидентов с фильтрацией и пагинацией."""
    query = select(Incident)
    count_query = select(func.count(Incident.id))

    if site_id:
        query = query.where(Incident.site_id == site_id)
        count_query = count_query.where(Incident.site_id == site_id)
    if status:
        query = query.where(Incident.status == status)
        count_query = count_query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
        count_query = count_query.where(Incident.severity == severity)
    if camera_id:
        query = query.where(Incident.camera_id == camera_id)
        count_query = count_query.where(Incident.camera_id == camera_id)

    total = db.scalar(count_query) or 0
    items = db.scalars(
        query.order_by(desc(Incident.updated_at), desc(Incident.created_at)).offset(offset).limit(limit)
    ).all()

    return [map_incident_to_read(inc, storage_provider) for inc in items], total


def get_incident_by_id(
    db: Session, incident_id: str, storage_provider: Optional[BaseStorageProvider] = None
) -> Optional[IncidentRead]:
    """Поиск инцидента по его ID."""
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        return None
    return map_incident_to_read(incident, storage_provider)


def create_incident(
    db: Session,
    incident_in: IncidentCreate,
    storage_provider: Optional[BaseStorageProvider] = None,
) -> IncidentRead:
    """Создание нового события нарушения."""
    # Генерация ID вида TK-xxxx если не передан
    incident_id = incident_in.id
    if not incident_id:
        short_num = str(uuid.uuid4().int)[:4]
        incident_id = f"TK-{short_num}"

    incident = Incident(
        id=incident_id,
        site_id=incident_in.site_id,
        camera_id=incident_in.camera_id,
        zone=incident_in.zone,
        title=incident_in.title,
        time=incident_in.time or datetime.now().strftime("%H:%M:%S"),
        severity=incident_in.severity,
        type=incident_in.type,
        description=incident_in.description,
        action=incident_in.action,
        image_key=incident_in.image_key,
        status=incident_in.status,
        box=incident_in.box,
        employee_name=incident_in.employee_name,
        employee_role=incident_in.employee_role,
        employee_number=incident_in.employee_number,
        employee_access=incident_in.employee_access,
        contact_name=incident_in.contact_name,
        contact_role=incident_in.contact_role,
        contact_radio=incident_in.contact_radio,
        contact_phone=incident_in.contact_phone,
        track_id=incident_in.track_id,
        confidence=incident_in.confidence,
        is_verified=incident_in.is_verified,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return map_incident_to_read(incident, storage_provider)


def create_or_merge_incident(
    db: Session,
    incident_in: IncidentCreate,
    storage_provider: Optional[BaseStorageProvider] = None,
) -> Tuple[IncidentRead, bool]:
    """Merge repeated detections from one camera into its recent open incident."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.execute(
        select(Camera.id).where(Camera.id == incident_in.camera_id).with_for_update()
    ).scalar_one_or_none()
    recent_open = db.scalar(
        select(Incident)
        .where(
            Incident.camera_id == incident_in.camera_id,
            Incident.title == incident_in.title,
            Incident.status.in_(("new", "working")),
        )
        .order_by(desc(Incident.updated_at))
        .limit(1)
        .with_for_update()
    )
    if recent_open and recent_open.updated_at:
        age = (now - recent_open.updated_at).total_seconds()
        if 0 <= age <= INCIDENT_MERGE_WINDOW_SECONDS:
            recent_open.time = incident_in.time
            recent_open.updated_at = now
            recent_open.severity = max(
                (recent_open.severity, incident_in.severity),
                key=lambda severity: {"info": 0, "warning": 1, "critical": 2}.get(severity, 0),
            )
            if incident_in.image_key:
                recent_open.image_key = incident_in.image_key
            if incident_in.box is not None:
                recent_open.box = incident_in.box
            if incident_in.track_id is not None:
                recent_open.track_id = incident_in.track_id
            if incident_in.confidence is not None:
                recent_open.confidence = incident_in.confidence
            db.commit()
            db.refresh(recent_open)
            return map_incident_to_read(recent_open, storage_provider), False

    return create_incident(db, incident_in, storage_provider), True


def update_incident_status(
    db: Session,
    incident_id: str,
    new_status: str,
    storage_provider: Optional[BaseStorageProvider] = None,
) -> Optional[IncidentRead]:
    """Смена статуса инцидента (new -> working -> resolved / dismissed)."""
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        return None
    incident.status = new_status
    db.commit()
    db.refresh(incident)
    return map_incident_to_read(incident, storage_provider)
