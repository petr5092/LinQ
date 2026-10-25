"""
Менеджер внешних уведомлений: маршрутизация оповещений в Telegram, NetIO и WebSocket.
"""

from __future__ import annotations

import os
import queue
import re
import threading
import time
from typing import Dict, Optional, Tuple

from app.config import settings, BASE_DIR
from app.services.notifications.base import BaseMessengerAdapter
from app.services.notifications.extensions import load_adapter
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
        self._started = False
        self._plugins_loaded = False
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
        self.adapters: Dict[str, BaseMessengerAdapter] = {"telegram": self.telegram}

        # Отслеживание активных оповещений: (camera_id, title) -> (incident_id, timestamp)
        # Гарантирует, что на длящееся нарушение отсылается ровно один алерт
        self._active_camera_alerts: Dict[Tuple[str, str], Tuple[str, float]] = {}

        # Инициализация NetIO
        netio_host = getattr(settings, "NETIO_HOST", None) or os.getenv("NETIO_HOST")
        self.netio = NetioClient(host=netio_host) if netio_host else None

    def start(self) -> None:
        """Запуск фоновых воркеров рассылки и long polling Telegram."""
        if self._started:
            return
        self._load_configured_adapters()
        self._stop = False
        self._started = True
        self._worker_thread = threading.Thread(target=self._delivery_loop, daemon=True, name="notify_delivery_worker")
        self._worker_thread.start()

        for adapter in self.adapters.values():
            if adapter.enabled:
                adapter.start()

    def stop(self) -> None:
        """Остановка сервиса уведомлений."""
        self._stop = True
        for adapter in self.adapters.values():
            adapter.stop()
        self._started = False

    def register_adapter(self, adapter: BaseMessengerAdapter) -> None:
        """Register a messenger adapter before the notification service starts."""
        if self._started:
            raise RuntimeError("Messenger adapters must be registered before NotificationManager.start().")
        if not isinstance(adapter, BaseMessengerAdapter):
            raise TypeError("adapter must inherit from BaseMessengerAdapter.")
        channel = getattr(adapter, "channel", None)
        if not isinstance(channel, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,49}", channel):
            raise ValueError("Adapter channel must be 1-50 lowercase letters, digits, '_' or '-' and start with a letter.")
        if channel == "netio":
            raise ValueError("'netio' is reserved for the hardware alarm integration.")
        if channel in self.adapters:
            raise ValueError(f"A messenger adapter is already registered for channel '{channel}'.")
        self.adapters[channel] = adapter

    def _load_configured_adapters(self) -> None:
        if self._plugins_loaded:
            return
        specs = os.getenv("LINQ_MESSENGER_ADAPTERS", "")
        for spec in filter(None, (value.strip() for value in specs.split(","))):
            self.register_adapter(load_adapter(spec, self))
        self._plugins_loaded = True

    def is_incident_notification_allowed(self, incident: dict) -> bool:
        """
        Проверяет по матрице настроек 'Зоны и правила', разрешена ли отправка
        уведомлений для данного нарушения на указанном участке.
        """
        zone = str(incident.get("zone") or incident.get("zone_id") or "").strip()
        if not zone:
            return True

        title = str(incident.get("title") or "").lower()
        desc = str(incident.get("description") or "").lower()
        rule_name = str(incident.get("rule_name") or incident.get("type") or "").lower()
        combined = f"{title} {desc} {rule_name}"

        # Правила, на которых обучена модель + радиометрический температурный контроль
        rule_mappings = [
            (
                "Контроль касок и жилетов (СИЗ)",
                ("каск", "жилет", "сиз", "helmet", "vest", "hardhat", "ppe_compliance", "респиратор"),
                ["Контроль касок и жилетов (СИЗ)", "Контроль касок и респираторов"],
            ),
            (
                "Опасное сближение с техникой",
                ("сближен", "proximity", "техник", "погрузчик", "авто", "машин"),
                ["Опасное сближение с техникой", "Опасное сближение с оборудованием"],
            ),
            (
                "Нахождение в опасной зоне",
                ("опасн", "периметр", "danger_zone", "запретн", "проникновен"),
                ["Нахождение в опасной зоне", "Вход в опасную зону"],
            ),
            (
                "Падение человека",
                ("падени", "лежит", "неподвиж", "fall", "fall_detection"),
                ["Падение человека"],
            ),
            (
                "Температурный контроль и перегрев",
                ("температур", "перегрев", "тепловиз", "thermal", "жар", "градус"),
                ["Температурный контроль и перегрев", "Температурный контроль", "Перегрев оборудования"],
            ),
        ]

        matched_aliases: List[str] = []
        for rule_label, keywords, aliases in rule_mappings:
            if any(kw in combined for kw in keywords):
                matched_aliases.extend(aliases)

        # Прямое совпадение по заголовку или названию правила (для пользовательских правил)
        raw_title = str(incident.get("title") or "").strip()
        if raw_title and raw_title not in matched_aliases:
            matched_aliases.append(raw_title)

        # Если хотя бы один алиас или правило для этой зоны отключено — подавляем отправку
        for alias in matched_aliases:
            if not self.store.is_notification_enabled_for_zone(zone, alias):
                return False

        return True

    def dispatch_incident(self, incident: dict, snapshot_path: Optional[str] = None) -> None:
        """Постановка инцидента в очередь внешней рассылки (только при старте нового нарушения)."""
        if not self.is_incident_notification_allowed(incident):
            return

        cam_id = str(incident.get("camera_id") or "")
        title = str(incident.get("title") or "")
        key = (cam_id, title)

        # Если по этой камере и данному нарушению уже активен алерт в пределах кулдауна — нарушение продолжается.
        # Не спамим новыми сообщениями, а только обновляем данные текущего инцидента.
        existing = self._active_camera_alerts.get(key)
        cooldown = float(os.getenv("COOLDOWN_SECONDS", "20"))
        now_ts = time.time()

        if existing:
            existing_id, alert_time = existing
            if now_ts - alert_time < cooldown:
                incident_id = str(incident.get("id") or incident.get("event_id") or "")
                if incident_id and incident_id != existing_id:
                    self._active_camera_alerts[key] = (incident_id, alert_time)
                self.refresh_incident(incident)
                return
            else:
                self._active_camera_alerts.pop(key, None)

        eid = str(incident.get("id") or incident.get("event_id") or "")
        if key[0] and eid:
            self._active_camera_alerts[key] = (eid, now_ts)

        try:
            self.q.put_nowait({
                "kind": "incident",
                "event": incident,
                "snapshot_path": snapshot_path,
            })
        except queue.Full:
            print("[NotificationManager] Очередь рассылки переполнена!")

    def refresh_incident(self, incident: dict) -> None:
        """Update the existing notification for a repeated detection."""
        if not self.is_incident_notification_allowed(incident):
            return
        try:
            self.q.put_nowait({"kind": "incident_update", "event": incident})
        except queue.Full:
            print("[NotificationManager] Очередь рассылки переполнена!")

    def resolve_camera_alert(self, camera_id: str, title: Optional[str] = None) -> None:
        """Сброс активного алерта при прекращении нарушения на камере."""
        for k in list(self._active_camera_alerts.keys()):
            if k[0] == camera_id and (title is None or k[1] == title):
                self._active_camera_alerts.pop(k, None)

    def reset_active_alerts(self) -> None:
        """Сброс всех активных алертов."""
        self._active_camera_alerts.clear()

    def update_incident_status(self, event_id: str, new_status: str, operator_name: Optional[str] = None) -> None:
        """Queue status updates for all channels that support message editing."""
        if new_status in ("resolved", "dismissed"):
            for k, v in list(self._active_camera_alerts.items()):
                if v[0] == event_id:
                    self._active_camera_alerts.pop(k, None)

        try:
            self.q.put_nowait({
                "kind": "status_update",
                "event": {
                    "id": event_id,
                    "status": new_status,
                    "assigned_to": f"@{operator_name}" if operator_name and not operator_name.startswith("@") else operator_name,
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
                elif kind == "incident_update":
                    self._refresh_incident_messages(task["event"])
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

        snap = snapshot_path if (snapshot_path and os.path.isfile(snapshot_path)) else None
        if not snap:
            candidates = []
            if snapshot_path:
                candidates.append(snapshot_path)
            for k in ("snapshot_path", "snapshot_url", "image_key"):
                val = event.get(k)
                if val and val not in candidates:
                    candidates.append(val)

            for val in candidates:
                if isinstance(val, str):
                    if os.path.isfile(val):
                        snap = val
                        break
                    rel = val.replace("/static/snapshots/", "").replace("/images/", "").lstrip("/\\")
                    for base in (
                        str(settings.LOCAL_SNAPSHOTS_DIR),
                        os.path.join(str(BASE_DIR), "storage", "snapshots"),
                        os.path.join(str(BASE_DIR), "frontend", "public", "images"),
                        os.path.join(str(BASE_DIR), "frontend", "public"),
                        os.path.join(str(BASE_DIR), "storage", "demo_snapshots"),
                    ):
                        for ext in ("", ".jpg", ".png", ".jpeg"):
                            cand = os.path.join(base, rel + ext)
                            if os.path.isfile(cand):
                                snap = cand
                                break
                        if snap:
                            break
                if snap:
                    break

        for adapter in self.adapters.values():
            if not adapter.enabled:
                continue
            active_subs = self.store.list_subscribers(channel=adapter.channel, active=True)
            for sub in active_subs:
                sub_min_sev = SEV_ORDER.get(sub.get("min_severity", "low").lower(), 0)
                if event_sev_lvl >= sub_min_sev:
                    self._send_with_retry(adapter, sub, event, snap)

    def _send_with_retry(
        self,
        client: BaseMessengerAdapter,
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
        deliveries = self.store.get_deliveries_for_event(eid)
        if deliveries and not any(event.get(key) for key in ("rule_label", "rule_name", "title")):
            from app.db.models.incident import Incident
            from app.db.session import SessionLocal
            from app.services.incident_service import map_incident_to_read

            with SessionLocal() as db:
                incident = db.get(Incident, eid)
                if incident:
                    full_event = map_incident_to_read(incident).model_dump(mode="json")
                    full_event.update(event)
                    full_event.update(
                        camera_name=incident.camera.name if incident.camera else incident.camera_id,
                        zone_name=incident.zone,
                        rule_label=incident.title,
                        timestamp_str=incident.time,
                    )
                    event = full_event
        for d in deliveries:
            adapter = self.adapters.get(d["channel"])
            if adapter and d.get("message_id"):
                try:
                    adapter.update_alert(d, event)
                except Exception as e:
                    print(f"[NotificationManager] Не удалось обновить сообщение в чате {d['chat_id']}: {e}")

    def _on_telegram_status_change(self, event_id: str, new_status: str, operator_name: str) -> None:
        """Callback от Telegram inline кнопок: сохраняем статус в БД и рассылаем в WS."""
        from app.db.session import SessionLocal
        from app.db.models.incident import Incident
        from sqlalchemy import select

        # Маппинг статусов Telegram в модель БД:
        # 'confirmed' / 'c' -> status='working', is_verified=True
        # 'acknowledged' / 'w' -> status='working', is_verified=False
        # 'false_positive' / 'dismissed' / 'f' -> status='dismissed', is_verified=False
        # 'resolved' / 'r' -> status='resolved', is_verified=True
        is_verified = False
        db_status = "working"
        if new_status in ("confirmed", "c"):
            db_status = "working"
            is_verified = True
        elif new_status in ("acknowledged", "w", "working"):
            db_status = "working"
            is_verified = False
        elif new_status in ("false_positive", "dismissed", "f"):
            db_status = "dismissed"
            is_verified = False
        elif new_status in ("resolved", "r"):
            db_status = "resolved"
            is_verified = True

        try:
            full_dict = None
            with SessionLocal() as db:
                inc = db.scalar(select(Incident).where(Incident.id == event_id))
                if inc:
                    inc.status = db_status
                    inc.is_verified = is_verified
                    if operator_name:
                        inc.contact_name = f"@{operator_name}"
                        inc.contact_role = "Оператор (Telegram)"
                    db.commit()
                    db.refresh(inc)
                    from app.services.incident_service import map_incident_to_read
                    full_dict = map_incident_to_read(inc).model_dump(mode="json")

            # Refresh delivered notifications and remove channel-specific action controls.
            self.update_incident_status(event_id, db_status, operator_name)

            # Широковещательное обновление UI через WebSocket
            update_payload = full_dict or {
                "id": event_id,
                "status": db_status,
                "is_verified": is_verified,
                "contact_name": f"@{operator_name}" if operator_name else None,
            }
            ws_notifier.broadcast_sync({
                "event": "INCIDENT_STATUS_UPDATED",
                "data": update_payload,
            })
            ws_notifier.broadcast_sync({
                "event": "INCIDENT_STATUS_CHANGED",
                "data": update_payload,
            })
        except Exception as e:
            print(f"[NotificationManager] Ошибка синхронизации статуса с БД: {e}")

    def sync_open_incidents(self) -> int:
        """Синхронизирует открытые нарушения из журнала с подключенными каналами оповещений."""
        from app.db.session import SessionLocal
        from app.db.models.incident import Incident
        from app.services.incident_service import map_incident_to_read
        from sqlalchemy import select, desc

        with SessionLocal() as db:
            open_incs = db.scalars(
                select(Incident)
                .where(Incident.status.in_(("new", "working")))
                .order_by(desc(Incident.created_at))
                .limit(20)
            ).all()

            synced = 0
            for inc in open_incs:
                inc_dict = map_incident_to_read(inc).model_dump(mode="json")
                deliveries = self.store.get_deliveries_for_event(inc.id)
                if deliveries:
                    self.refresh_incident(inc_dict)
                else:
                    self.dispatch_incident(inc_dict)
                synced += 1
            return synced

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
            adapter = self.adapters.get(s["channel"])
            if adapter and adapter.enabled:
                if self._send_with_retry(adapter, s, test_event):
                    sent += 1
        return sent

    def info(self) -> dict:
        """Сводка состояния каналов и подписчиков."""
        channels = {name: adapter.info() for name, adapter in self.adapters.items()}
        return {
            "telegram": channels["telegram"],
            "channels": channels,
            "netio": {"configured": bool(self.netio)},
            "subscribers": self.store.list_subscribers(),
            "stats": self.store.delivery_stats(),
            "deliveries": self.store.list_deliveries(limit=25),
        }


notification_manager = NotificationManager()
