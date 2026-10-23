import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.incident import (
    IncidentRead,
    IncidentCreate,
    IncidentUpdateStatus,
)
from app.schemas.common import PaginatedResponse
from app.services.incident_service import (
    list_incidents,
    get_incident_by_id,
    create_incident,
    update_incident_status,
)
from app.services.notifier import notifier
from app.storage.factory import get_storage_provider

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=PaginatedResponse[IncidentRead])
def get_incidents_list(
    site_id: Optional[str] = Query(None, description="Фильтр по площадке"),
    status: Optional[str] = Query(None, description="Фильтр по статусу (new, working, resolved, dismissed)"),
    severity: Optional[str] = Query(None, description="Фильтр по критичности (critical, warning, info)"),
    camera_id: Optional[str] = Query(None, description="Фильтр по камере"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(50, ge=1, le=100, description="Элементов на странице"),
    db: Session = Depends(get_db),
):
    """
    Получение журнала инцидентов с гибкой фильтрацией и пагинацией.
    """
    storage = get_storage_provider()
    offset = (page - 1) * size
    items, total = list_incidents(
        db=db,
        site_id=site_id,
        status=status,
        severity=severity,
        camera_id=camera_id,
        limit=size,
        offset=offset,
        storage_provider=storage,
    )

    pages = math.ceil(total / size) if size > 0 else 1
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    """Получение детальной информации об инциденте."""
    storage = get_storage_provider()
    incident = get_incident_by_id(db=db, incident_id=incident_id, storage_provider=storage)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Инцидент с ID '{incident_id}' не найден",
        )
    return incident


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def register_incident(incident_in: IncidentCreate, db: Session = Depends(get_db)):
    """
    Регистрация инцидента (вызывается CV Engine при детекции нарушения).
    Автоматически инициирует широковещательное WebSocket-оповещение операторов.
    """
    storage = get_storage_provider()
    incident_read = create_incident(db=db, incident_in=incident_in, storage_provider=storage)

    # Отправляем оповещение диспетчерам через WebSocket
    await notifier.broadcast({
        "event": "INCIDENT_NEW",
        "data": incident_read.model_dump(mode="json")
    })

    return incident_read


@router.patch("/{incident_id}/status", response_model=IncidentRead)
async def change_incident_status(
    incident_id: str,
    update_data: IncidentUpdateStatus,
    db: Session = Depends(get_db),
):
    """
    Смена статуса инцидента диспетчером:
    - 'new' -> 'working' (взят в работу)
    - 'working' -> 'resolved' (устранено)
    - 'new'/'working' -> 'dismissed' (ложная тревога)
    """
    valid_statuses = {"new", "working", "resolved", "dismissed"}
    if update_data.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый статус '{update_data.status}'. Допустимые: {valid_statuses}",
        )

    storage = get_storage_provider()
    updated = update_incident_status(
        db=db,
        incident_id=incident_id,
        new_status=update_data.status,
        storage_provider=storage,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Инцидент с ID '{incident_id}' не найден",
        )

    # Оповещаем UI об изменении статуса
    await notifier.broadcast({
        "event": "INCIDENT_STATUS_CHANGED",
        "data": updated.model_dump(mode="json")
    })

    return updated
