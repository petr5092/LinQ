from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.notifications import notification_manager

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class SubscriberUpdateRequest(BaseModel):
    min_severity: Optional[str] = None
    active: Optional[bool] = None
    delete: Optional[bool] = False


class ZoneRuleToggleRequest(BaseModel):
    zone: str
    rule: str
    enabled: bool


class TestNotificationRequest(BaseModel):
    subscriber_id: Optional[int] = None


@router.get("/rules")
def get_notification_zone_rules():
    """Получение матрицы включения/отключения уведомлений по зонам и правилам."""
    return notification_manager.store.get_zone_rules()


@router.post("/rules")
def set_notification_zone_rule(req: ZoneRuleToggleRequest):
    """Переключение отправки уведомлений для конкретного правила в зоне."""
    notification_manager.store.set_zone_rule(req.zone, req.rule, req.enabled)
    return {"ok": True, "zone": req.zone, "rule": req.rule, "enabled": req.enabled}


@router.get("/status")
def get_notifications_status():
    """Получение сводки состояния каналов оповещения (Telegram, NetIO) и списка подписчиков."""
    return notification_manager.info()


@router.post("/test")
def send_test_notification(req: TestNotificationRequest = TestNotificationRequest()):
    """Отправка тестового оповещения в подключенные каналы связи."""
    sent_count = notification_manager.send_test(subscriber_id=req.subscriber_id)
    return {"ok": True, "sent_to_count": sent_count}


@router.post("/sync")
def sync_notifications():
    """Синхронизация всех активных нарушений из журнала с каналами оповещений."""
    count = notification_manager.sync_open_incidents()
    return {"ok": True, "synced_count": count}


@router.get("/deliveries")
def get_deliveries(limit: int = 50, failed_only: bool = False):
    """Журнал доставок и ошибок оповещений."""
    return notification_manager.store.list_deliveries(limit=limit, failed_only=failed_only)


@router.post("/subscribers/{subscriber_id}")
def update_subscriber(subscriber_id: int, req: SubscriberUpdateRequest):
    """Обновление порога фильтрации или удаление подписчика."""
    if req.delete:
        notification_manager.store.delete_subscriber(subscriber_id)
        return {"ok": True, "message": f"Подписчик {subscriber_id} удален"}

    fields = {}
    if req.min_severity is not None:
        fields["min_severity"] = req.min_severity.lower()
    if req.active is not None:
        fields["active"] = req.active

    if fields:
        notification_manager.store.update_subscriber(subscriber_id, **fields)

    return {"ok": True, "subscriber_id": subscriber_id}
