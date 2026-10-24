"""CV process boundary: receive completed incidents and store their evidence."""
import base64
import binascii
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import cv2
import numpy as np

from app.db.session import get_db
from app.db.models.camera import Camera
from app.schemas.incident import IncidentCreate, IncidentRead
from app.services.incident_service import create_incident, get_incident_by_id
from app.services.notifications import notification_manager
from app.services.notifier import notifier
from app.storage.factory import get_storage_provider

router = APIRouter(prefix='/worker', tags=['CV Worker'])


class WorkerIncident(BaseModel):
    incident: IncidentCreate
    jpeg_base64: str = Field(..., min_length=4, max_length=7_000_000)


@router.post('/incidents', response_model=IncidentRead, status_code=201)
async def ingest_incident(payload: WorkerIncident, db: Session = Depends(get_db)):
    event = payload.incident
    if not event.id or not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', event.id):
        raise HTTPException(422, 'A stable safe event ID is required')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', event.camera_id):
        raise HTTPException(422, 'Invalid camera ID')
    camera = db.get(Camera, event.camera_id)
    if camera is None or camera.site_id != event.site_id:
        raise HTTPException(422, 'Register this camera and site before starting CV')
    storage = get_storage_provider()
    previous = get_incident_by_id(db, event.id, storage)
    if previous:
        return previous  # a retry must not broadcast or notify twice
    try:
        jpeg = base64.b64decode(payload.jpeg_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, 'Invalid base64 snapshot')
    if not jpeg.startswith(b'\xff\xd8') or len(jpeg) > 5_000_000:
        raise HTTPException(422, 'Expected a JPEG snapshot up to 5 MB')
    frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(422, 'Invalid JPEG snapshot')
    key = storage.save_snapshot_key(frame, event.id, event.camera_id)
    event = event.model_copy(update={'image_key': key})
    try:
        created = create_incident(db, event, storage)
    except IntegrityError:
        db.rollback()
        previous = get_incident_by_id(db, event.id, storage)
        if previous:
            return previous
        raise
    data = created.model_dump(mode='json')
    await notifier.broadcast({'event': 'INCIDENT_CREATED', 'data': data})
    notification_manager.dispatch_incident(data)
    return created
