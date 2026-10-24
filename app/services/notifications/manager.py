"""
Менеджер внешних уведомлений: маршрутизация оповещений в Telegram, NetIO и WebSocket.
"""

from __future__ import annotations

import os
from pathlib import Path
import queue
import threading
import time
from typing import Any, Dict, List, Optional

from app.config import settings, BASE_DIR
from app.services.notifications.netio import ApiError, NetioClient
from app.services.notifications.store import NotificationStore
from app.services.notifications.telegram import TelegramClient, SEV_ORDER
from app.services.notifier import notifier as ws_notifier


class NotificationManager:
    """Центральный координатор системы оповещения."""

    def __init__(self) -> None:
        self.store = NotificationStore()
        self.q: queue.Queue = queue.Queue(maxsize=1000)
        self._stop = False
        self._worker_thread: Optional[threading.Thread] = None

        # Инициализация Telegram
        tg_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None) or os.getenv("LINQ_TG_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        tg_base = getattr(settings, "TELEGRAM_API_BASE", "https://api.telegram.org")
        pub_url = getattr(settings, "PUBLIC_DASHBOARD_URL", None) or os.getenv("PUBLIC_DASHBOARD_URL") or os.getenv("LINQ_PUBLIC_URL", "http://localhost:3000")

        self.telegram = TelegramClient(
            token=tg_token or "",
            store=self.store,
            base_url=tg_base,
            public_url=pub_url,
            on_status_change=self._on_telegram_status_change,
        )

        # Инициализация NetIO
        netio_host = getattr(settings, "NETIO_HOST", None) or os.getenv("NETIO_HOST")
        self.netio = NetioClient(host=netio_host) if netio_host else None

    def start(self) -> None:
        """Запуск фоновых воркеров рассылки и long polling Telegram."""
        self._stop = False
        self._worker_thread = threading.Thread(target=self._delivery_loop, daemon=True, name="notify_delivery_worker")
        self._worker_thread.start()

        if self.telegram.token:
            self.telegram.start()

    def stop(self) -> None:
        """Остановка сервиса уведомлений."""
        self._stop = True
        self.telegram.stop()

    def dispatch_incident(self, incident: dict, snapshot_path: Optional[str] = None) -> None:
        """Постановка инцидента в очередь внешней рассылки."""
        try:
            self.q.put_nowait({
                "kind": "incident",
                "event": incident,
                "snapshot_path": snapshot_path,
            })
        except queue.Full:
            print("[NotificationManager] Очередь рассылки переполнена!")

    def update_incident_status(self, event_id: str, new_status: str, operator_name: Optional[str] = None) -> None:
        """Обновление статуса в отправленных сообщениях (Telegram)."""
        try:
            self.q.put_nowait({
                "kind": "status_update",
                "event": {
                    "id": event_id,
                    "status": new_status,
                    "assigned_to": operator_name,
                },
            })
        except queue.Full:
            pass

    def _delivery_loop(self) -> None:
        while not self._stop:
            try:
                task = self.q.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                kind = task.get("kind")
                if kind == "incident":
                    self._deliver_incident(task["event"], task.get("snapshot_path"))
                elif kind == "status_update":
                    self._refresh_incident_messages(task["event"])
            except Exception as e:
                print(f"[NotificationManager] Необработанная ошибка рассылки: {e}")

    def _deliver_incident(self, event: dict, snapshot_path: Optional[str] = None) -> None:
        sev_str = str(event.get("severity", "low")).lower()
        event_sev_lvl = SEV_ORDER.get(sev_str, 0)

        # Срабатывание сирены при критическом инциденте
        if event_sev_lvl >= SEV_ORDER["critical"] and self.netio:
            self.netio.trigger_siren()

        # Рассылка по активным Telegram-подписчикам
        if self.telegram.token:
            active_subs = self.store.list_subscribers(channel="telegram", active=True)
            snap = snapshot_path
            if not snap and event.get("image_key"):
                cand = os.path.join(str(settings.LOCAL_SNAPSHOTS_DIR), str(event["image_key"]))
                if os.path.isfile(cand):
                    snap = cand
            for sub in active_subs:
                sub_min_sev = SEV_ORDER.get(sub.get("min_severity", "low").lower(), 0)
                if event_sev_lvl >= sub_min_sev:
                    self._send_with_retry(self.telegram, sub, event, snap)

    def _send_with_retry(
        self,
        client: TelegramClient,
        subscriber: dict,
        event: dict,
        snapshot_path: Optional[str] = None,
    ) -> bool:
        eid = str(event.get("id") or event.get("event_id") or "0")
        chat_id = subscriber["chat_id"]
        last_error = None

        for attempt in range(3):
            t0 = time.perf_counter()
            try:
                msg_id, kind = client.send_alert(subscriber, event, snapshot_path)
                lat_ms = (time.perf_counter() - t0) * 1000.0
                self.store.add_delivery(
                    event_id=eid,
                    channel=client.channel,
                    chat_id=chat_id,
                    message_id=msg_id,
                    kind=kind,
                    ok=True,
                    latency_ms=round(lat_ms, 1),
                )
                return True
            except ApiError as e:
                last_error = str(e)
                if client.is_gone(e):
                    self.store.set_subscriber_active(client.channel, chat_id, False)
                    break
                if attempt < 2:
                    wait_time = min(e.retry_after or (attempt + 1) * 2.0, 30.0)
                    time.sleep(wait_time)
            except Exception as e:
                last_error = str(e)
                time.sleep(1.0)

        self.store.add_delivery(
            event_id=eid,
            channel=client.channel,
            chat_id=chat_id,
            message_id=None,
            kind="failed",
            ok=False,
            error=last_error,
        )
        return False

    def _refresh_incident_messages(self, event: dict) -> None:
        eid = str(event.get("id") or event.get("event_id") or "0")
        deliveries = self.store.get_deliveries_for_event(eid, channel="telegram")
        for d in deliveries:
            if d.get("message_id"):
                try:
                    self.telegram.update_alert(d, event)
                except Exception as e:
                    print(f"[NotificationManager] Не удалось обновить сообщение в чате {d['chat_id']}: {e}")

    def _on_telegram_status_change(self, event_id: str, new_status: str, operator_name: str) -> None:
        """Callback от Telegram inline кнопок: сохраняем статус в БД и рассылаем в WS."""
        from app.db.session import SessionLocal
        from app.db.models.incident import Incident
        from datetime import datetime

        try:
            with SessionLocal() as db:
                inc = db.query(Incident).filter(Incident.id == event_id).first()
                if inc:
                    inc.status = new_status
                    if not inc.assigned_to:
                        inc.assigned_to = f"tg:@{operator_name}"
                    if new_status == "acknowledged" and not inc.acknowledged_at:
                        inc.acknowledged_at = datetime.utcnow()
                    elif new_status in ("resolved", "confirmed") and not inc.resolved_at:
                        inc.resolved_at = datetime.utcnow()
                    db.commit()

            # Обновляем все Telegram сообщения
            self.update_incident_status(event_id, new_status, operator_name)
        except Exception as e:
            print(f"[NotificationManager] Ошибка синхронизации статуса с БД: {e}")

    def send_test(self, subscriber_id: Optional[int] = None) -> int:
        """Отправка тестового оповещения всем активным или конкретному подписчику."""
        test_event = {
            "id": "test_alert_01",
            "rule_name": "Тестовое оповещение",
            "rule_label": "Проверка системы оповещения LinQ",
            "severity": "low",
            "camera_name": "Тестовая камера",
            "zone_name": "Периметр безопасности",
            "timestamp_str": time.strftime("%H:%M:%S %d.%m.%Y"),
            "status": "new",
        }

        subs = self.store.list_subscribers(active=True)
        if subscriber_id:
            subs = [s for s in subs if s["id"] == subscriber_id]

        sent = 0
        for s in subs:
            if s["channel"] == "telegram":
                if self._send_with_retry(self.telegram, s, test_event):
                    sent += 1
        return sent

    def info(self) -> dict:
        """Сводка состояния каналов и подписчиков."""
        return {
            "telegram": self.telegram.info(),
            "netio": {"configured": bool(self.netio)},
            "subscribers": self.store.list_subscribers(),
            "stats": self.store.delivery_stats(),
        }


notification_manager = NotificationManager()
