"""CV process boundary: receive completed incidents and store their evidence."""
import base64
import binascii
import logging
import re
import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.db.session import get_db
from app.db.models.camera import Camera
from app.schemas.incident import IncidentCreate, IncidentRead
from app.services.incident_service import create_or_merge_incident, get_incident_by_id
from app.services.notifications import notification_manager
from app.services.notifier import notifier
from app.services.browser_camera import (
    BrowserCameraConfigurationError,
    process_browser_frame,
)
from app.storage.factory import get_storage_provider

router = APIRouter(prefix='/worker', tags=['CV Worker'])
log = logging.getLogger(__name__)


class WorkerIncident(BaseModel):
    incident: IncidentCreate
    jpeg_base64: str = Field(..., min_length=4, max_length=7_000_000)


@router.post('/incidents', response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def ingest_incident(
    payload: WorkerIncident,
    response: Response,
    db: Session = Depends(get_db),
):
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
        response.status_code = status.HTTP_200_OK
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
        incident, created = create_or_merge_incident(db, event, storage)
    except IntegrityError:
        db.rollback()
        previous = get_incident_by_id(db, event.id, storage)
        if previous:
            response.status_code = status.HTTP_200_OK
            return previous
        raise
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    data = incident.model_dump(mode='json')
    await notifier.broadcast({
        'event': 'INCIDENT_CREATED' if created else 'INCIDENT_UPDATED',
        'data': data,
    })
    if created:
        notification_manager.dispatch_incident(data)
    else:
        notification_manager.refresh_incident(data)
    return incident


@router.post('/browser-frame/{camera_id}')
async def ingest_browser_frame(
    camera_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Process one JPEG frame captured by the operator's browser."""
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Сначала зарегистрируйте камеру в системе.')
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'image/jpeg':
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, 'Ожидается кадр image/jpeg.')
    jpeg = bytearray()
    async for chunk in request.stream():
        jpeg.extend(chunk)
        if len(jpeg) > 2_000_000:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, 'Размер JPEG не должен превышать 2 МБ.')
    if not jpeg:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, 'Размер JPEG должен быть от 1 байта до 2 МБ.')
    try:
        result = await run_in_threadpool(process_browser_frame, camera, jpeg)
    except BrowserCameraConfigurationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:
        log.exception('Browser camera frame processing failed camera=%s', camera_id)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'Не удалось обработать кадр камеры.') from exc
    return result
