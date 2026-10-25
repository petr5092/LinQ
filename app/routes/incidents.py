import csv
import io
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import Response
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
    create_or_merge_incident,
    update_incident_status,
)
from app.services.notifications import notification_manager
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


@router.get("/export/csv")
def export_incidents_csv(
    site_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Выгрузка журнала инцидентов в CSV-формате (с поддержкой UTF-8 BOM для Excel)."""
    storage = get_storage_provider()
    items, _ = list_incidents(
        db=db,
        site_id=site_id,
        status=status,
        severity=severity,
        camera_id=camera_id,
        limit=50000,
        offset=0,
        storage_provider=storage,
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Время", "Камера", "Площадка", "Тип нарушения", "Критичность", "Статус", "Снапшот URL"])
    for item in items:
        ts_str = getattr(item, "time", "") or str(getattr(item, "created_at", ""))
        writer.writerow([
            item.id,
            ts_str,
            item.camera_id,
            item.site_id,
            item.type,
            item.severity,
            item.status,
            item.snapshot_url or "",
        ])

    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="linq_safety_incidents.csv"'},
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
async def register_incident(
    incident_in: IncidentCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Регистрация инцидента (вызывается CV Engine при детекции нарушения).
    Автоматически инициирует широковещательное WebSocket и Telegram оповещение операторов.
    """
    storage = get_storage_provider()
    incident_read, created = create_or_merge_incident(
        db=db,
        incident_in=incident_in,
        storage_provider=storage,
    )
    incident_dict = incident_read.model_dump(mode="json")

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    await notifier.broadcast({
        "event": "INCIDENT_CREATED" if created else "INCIDENT_UPDATED",
        "data": incident_dict,
    })

    if created:
        notification_manager.dispatch_incident(incident_dict)
    else:
        notification_manager.refresh_incident(incident_dict)

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
        "event": "INCIDENT_STATUS_UPDATED",
        "data": updated.model_dump(mode="json")
    })

    # Обновляем статус в Telegram-сообщениях
    notification_manager.update_incident_status(
        incident_id,
        update_data.status,
        getattr(update_data, "operator_name", None),
    )

    return updated
