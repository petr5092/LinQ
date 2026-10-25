"""
Telegram-бот оперативного оповещения LinQ Safety Guard на long polling.
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.notifications.base import BaseMessengerAdapter
from app.services.notifications.netio import ApiError, post_json, post_multipart
from app.services.notifications.store import NotificationStore

SEV_LEVELS = {"all": "low", "low": "low", "medium": "medium", "high": "high", "critical": "critical"}
SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
SEV_ICON = {"critical": "🚨", "high": "🔶", "warning": "🟡", "medium": "🟡", "low": "⚪"}
STATUS_MAP = {"c": "confirmed", "f": "false_positive", "w": "acknowledged", "r": "resolved"}
STATUS_TEXT = {
    "confirmed": "✅ Подтверждено",
    "false_positive": "✖️ Ложная тревога",
    "dismissed": "✖️ Ложная тревога",
    "acknowledged": "👷 Принято в работу",
    "working": "👷 В работе",
    "resolved": "✔️ Устранено",
    "new": "⚠️ Ожидает проверки",
}


class TelegramClient(BaseMessengerAdapter):
    channel = "telegram"

    def __init__(
        self,
        token: str,
        store: NotificationStore,
        base_url: str = "https://api.telegram.org",
        public_url: Optional[str] = None,
        on_status_change: Optional[Any] = None,
    ) -> None:
        self.token = token.strip()
        self.store = store
        self.base = base_url.rstrip("/")
        self.public_url = public_url
        self.on_status_change = on_status_change

        self.username: Optional[str] = None
        self.status: str = "starting"
        self.error: Optional[str] = None
        self._stop: bool = False
        self._thread: Optional[threading.Thread] = None

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def start(self) -> None:
        if not self.token:
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="telegram_poller")
        self._thread.start()

    def stop(self) -> None:
        self._stop = True

    def api(self, method: str, payload: Optional[dict] = None, timeout: float = 40.0) -> Any:
        url = f"{self.base}/bot{self.token}/{method}"
        code, raw = post_json(url, payload or {}, timeout=timeout)
        try:
            d = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApiError(f"{method}: HTTP {code}", code)

        if not d.get("ok"):
            params = d.get("parameters") or {}
            raise ApiError(
                d.get("description", "ошибка API Telegram"),
                d.get("error_code"),
                params.get("retry_after"),
            )
        return d["result"]

    def info(self) -> dict:
        u = self.username
        return {
            "configured": bool(self.token),
            "status": self.status,
            "error": self.error,
            "username": u,
            "links": {
                "group": f"https://t.me/{u}?startgroup=linq" if u else None,
                "channel": f"https://t.me/{u}?startchannel=linq&admin=post_messages" if u else None,
                "private": f"https://t.me/{u}?start=linq" if u else None,
            },
        }

    def is_gone(self, e: Exception) -> bool:
        if isinstance(e, ApiError):
            m = str(e).lower()
            return e.code == 403 or "chat not found" in m or "kicked" in m or "deactivated" in m
        return False

    def _run_loop(self) -> None:
        offset = None
        while not self._stop:
            try:
                if self.status != "online":
                    me = self.api("getMe")
                    self.username = me["username"]
                    self.api("deleteWebhook")
                    self.api(
                        "setMyCommands",
                        {
                            "commands": [
                                {"command": "start", "description": "Подключить этот чат к уведомлениям"},
                                {"command": "status", "description": "Сводка безопасности и журнал нарушений"},
                                {"command": "sync", "description": "Синхронизировать нарушения из журнала"},
                                {"command": "level", "description": "Порог важности: all, medium, high, critical"},
                                {"command": "stop", "description": "Отключить уведомления"},
                            ]
                        },
                    )
                    self.status = "online"
                    self.error = None
                    print(f"[Telegram] Бот @{self.username} успешно запущен в режиме long polling")

                params = {
                    "timeout": 25,
                    "allowed_updates": ["message", "my_chat_member", "callback_query"],
                }
                if offset:
                    params["offset"] = offset

                updates = self.api("getUpdates", params, timeout=40.0)
                for upd in updates:
                    offset = upd["update_id"] + 1
                    try:
                        self.handle_update(upd)
                    except Exception as e:
                        print(f"[Telegram] Ошибка обработки обновления: {e}")

            except ApiError as e:
                self.status = "error"
                self.error = str(e)
                if e.code == 401:
                    print("[Telegram] Неверный токен бота, остановка")
                    return
                time.sleep(5.0)
            except Exception as e:
                self.status = "error"
                self.error = str(e)
                time.sleep(5.0)

    def handle_update(self, upd: dict) -> None:
        if "my_chat_member" in upd:
            return self.on_membership(upd["my_chat_member"])
        if "callback_query" in upd:
            return self.on_callback(upd["callback_query"])

        m = upd.get("message") or {}
        text = (m.get("text") or "").strip()
        if text.startswith("/"):
            parts = text.split(" ", 1)
            cmd = parts[0].split("@")[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            # Игнорируем команды для других ботов
            if "@" in parts[0] and parts[0].split("@")[1].lower() != (self.username or "").lower():
                return

            self.on_command(m, cmd, arg)

    def on_membership(self, member_upd: dict) -> None:
        chat = member_upd["chat"]
        new_status = member_upd.get("new_chat_member", {}).get("status")
        title = chat.get("title") or chat.get("username") or str(chat["id"])

        if new_status in ("member", "administrator"):
            self.store.upsert_subscriber(self.channel, chat["id"], title, chat["type"])
            self.send_message(
                chat["id"],
                "🚨 <b>LinQ Safety Guard подключен к чату.</b>\n"
                "Сюда будут поступать оперативные фотодоказательства нарушений ТБ с возможностью подтверждения.",
            )
        elif new_status in ("left", "kicked"):
            self.store.set_subscriber_active(self.channel, chat["id"], False)

    def on_command(self, message: dict, cmd: str, arg: str) -> None:
        chat = message["chat"]
        cid = chat["id"]
        title = chat.get("title") or chat.get("first_name") or str(cid)

        if cmd in ("/start", "/connect"):
            self.store.upsert_subscriber(self.channel, cid, title, chat["type"])
            self.send_message(
                cid,
                "✅ <b>Уведомления LinQ Safety Guard подключены.</b>\n"
                "Сюда приходят стоп-кадры нарушений с кнопками действий оператора.\n"
                "Команды: /status — сводка, /level — порог важности, /stop — отключить.",
            )
        elif cmd == "/stop":
            self.store.set_subscriber_active(self.channel, cid, False)
            self.send_message(cid, "Уведомления отключены. Чтобы вернуть: /start.")
        elif cmd in ("/status", "/stats"):
            sub = self.store.get_subscriber(self.channel, cid)
            state = "подключен" if sub and sub["active"] else "не подключен (/start)"
            lvl = sub["min_severity"] if sub else "—"

            journal_info = ""
            try:
                from app.db.session import SessionLocal
                from app.db.models.incident import Incident
                from sqlalchemy import select, func
                with SessionLocal() as db:
                    total = db.scalar(select(func.count(Incident.id))) or 0
                    open_cnt = db.scalar(select(func.count(Incident.id)).where(Incident.status.in_(("new", "working")))) or 0
                    new_cnt = db.scalar(select(func.count(Incident.id)).where(Incident.status == "new")) or 0
                    work_cnt = db.scalar(select(func.count(Incident.id)).where(Incident.status == "working")) or 0
                    resolved_cnt = db.scalar(select(func.count(Incident.id)).where(Incident.status == "resolved")) or 0
                    journal_info = (
                        f"\n\n<b>📊 Журнал нарушений:</b>\n"
                        f"• Всего зарегистрировано: <b>{total}</b>\n"
                        f"• Требуют реакции: <b>{open_cnt}</b> (новых: {new_cnt}, в работе: {work_cnt})\n"
                        f"• Устранено: <b>{resolved_cnt}</b>"
                    )
            except Exception:
                journal_info = "\n\nСистема видеоаналитики LinQ активна."

            self.send_message(
                cid,
                f"<b>Состояние бота:</b> {state}\n"
                f"<b>Текущий порог важности:</b> {lvl}"
                f"{journal_info}",
            )
        elif cmd in ("/sync", "/incidents", "/events"):
            try:
                from app.db.session import SessionLocal
                from app.db.models.incident import Incident
                from app.services.incident_service import map_incident_to_read
                from sqlalchemy import select, desc
                with SessionLocal() as db:
                    open_incidents = db.scalars(
                        select(Incident)
                        .where(Incident.status.in_(("new", "working")))
                        .order_by(desc(Incident.created_at))
                        .limit(5)
                    ).all()
                    if not open_incidents:
                        self.send_message(cid, "✅ <b>В журнале нет активных нарушений.</b> Все инциденты устранены.")
                    else:
                        self.send_message(cid, f"📋 <b>Активные нарушения из журнала ({len(open_incidents)}):</b>")
                        sub = self.store.get_subscriber(self.channel, cid)
                        if sub:
                            for inc in open_incidents:
                                inc_dict = map_incident_to_read(inc).model_dump(mode="json")
                                self.send_alert(sub, inc_dict)
            except Exception as e:
                self.send_message(cid, f"Ошибка синхронизации: {e}")
        elif cmd == "/level":
            if arg.lower() in SEV_LEVELS and self.store.get_subscriber(self.channel, cid):
                chosen_lvl = SEV_LEVELS[arg.lower()]
                sub = self.store.get_subscriber(self.channel, cid)
                self.store.update_subscriber(sub["id"], min_severity=chosen_lvl)
                self.send_message(cid, f"Порог важности обновлен: <b>{chosen_lvl}</b>.")
            else:
                self.send_message(cid, "Использование: /level all | low | medium | high | critical")
        elif cmd == "/help":
            self.send_message(
                cid,
                "/start — подключить чат\n"
                "/status — сводка состояния и статистика журнала\n"
                "/sync — синхронизировать открытые нарушения из журнала\n"
                "/level [уровень] — фильтр важности (low/medium/high/critical)\n"
                "/stop — отключить чат",
            )

    def on_callback(self, cq: dict) -> None:
        data = cq.get("data", "")
        # Формат callback: st:<event_id>:<c|f|w|r>
        match = re.fullmatch(r"st:([\w\-]+):([cfwr])", data)
        if not match:
            return self.api("answerCallbackQuery", {"callback_query_id": cq["id"]})

        event_id = match.group(1)
        action_code = match.group(2)
        new_status = STATUS_MAP.get(action_code, "confirmed")
        user = cq.get("from", {})
        operator_name = user.get("username") or user.get("first_name") or "Оператор"

        # Уведомляем систему об изменении статуса инцидента
        if self.on_status_change:
            try:
                self.on_status_change(event_id, new_status, operator_name)
            except Exception as e:
                print(f"[Telegram] Ошибка callback status change: {e}")

        status_text = STATUS_TEXT.get(new_status, new_status)
        self.api(
            "answerCallbackQuery",
            {"callback_query_id": cq["id"], "text": f"Статус обновлен: {status_text}"},
        )

    def send_message(self, chat_id: str | int, text: str) -> None:
        try:
            self.api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        except Exception as e:
            print(f"[Telegram] Не удалось отправить сообщение: {e}")

    def format_caption(self, event: dict) -> str:
        sev = str(event.get("severity", "medium")).lower()
        rule_label = (
            event.get("title")
            or event.get("rule_label")
            or event.get("rule_name")
            or "Нарушение ТБ"
        )
        cam_name = (
            event.get("camera_name")
            or event.get("camera_id")
            or "Камера"
        )
        cam_id = str(event.get("camera_id") or "")
        zone = (
            event.get("zone")
            or event.get("zone_name")
            or event.get("zone_id")
            or ""
        )
        ts_str = (
            event.get("timestamp_str")
            or event.get("time")
            or time.strftime("%H:%M:%S %d.%m.%Y")
        )
        status = event.get("status", "new")
        operator = (
            event.get("contact_name")
            or event.get("assigned_to")
            or event.get("operator_notes")
        )
        desc = str(event.get("description") or "")
        action = event.get("action")

        title_lower = rule_label.lower()
        desc_lower = desc.lower()
        cam_id_lower = cam_id.lower()

        is_thermal = (
            "перегрев" in title_lower
            or "перегрев" in desc_lower
            or "температур" in title_lower
            or "температур" in desc_lower
            or "thermal" in cam_id_lower
            or "тепловиз" in cam_id_lower
            or event.get("type") in ("thermal", "temperature")
        )

        if is_thermal:
            icon = "🔥"
            # Извлекаем температуру, порог и величину превышения
            combined = f"{rule_label} {desc}"
            cur_temp = event.get("max_temperature_c") or event.get("temperature")
            threshold = event.get("threshold_c") or event.get("threshold")
            excess = event.get("excess_c") or event.get("diff_c")

            if excess is None:
                m_exc = re.search(
                    r"превышен[ие|я]*[:\s]*\+?(\d+(?:\.\d+)?)|(?:\+|\b)(\d+(?:\.\d+)?)\s*°?\s*[cCсС]\s*выше",
                    combined,
                    re.IGNORECASE,
                )
                if not m_exc:
                    m_exc = re.search(r"\+(\d+(?:\.\d+)?)\s*°?\s*[cCсС]", combined)
                if m_exc:
                    excess = float(m_exc.group(1) or m_exc.group(2))

            if cur_temp is None:
                m_cur = re.search(
                    r"(?:температура(?:\s*достигла|\s*составляет)?|\:)\s*(\d+(?:\.\d+)?)\s*°?\s*[cCсС]",
                    combined,
                    re.IGNORECASE,
                )
                if m_cur:
                    cur_temp = float(m_cur.group(1))

            if threshold is None:
                m_thr = re.search(r"порог[еа]?\s*[:\s]*(\d+(?:\.\d+)?)\s*°?\s*[cCсС]?", combined, re.IGNORECASE)
                if m_thr:
                    threshold = float(m_thr.group(1))

            if excess is None and cur_temp is not None and threshold is not None:
                diff = round(float(cur_temp) - float(threshold), 1)
                if diff > 0:
                    excess = diff

            lines = [
                f"{icon} <b>{html.escape(rule_label)}</b>",
                f"📹 Камера: <b>{html.escape(cam_name)}</b>" + (f" (зона: {html.escape(zone)})" if zone else ""),
            ]

            if cur_temp is not None and threshold is not None:
                lines.append(f"🌡 Температура: <b>{float(cur_temp):.1f} °C</b> (порог: <b>{float(threshold):.1f} °C</b>)")
            elif cur_temp is not None:
                lines.append(f"🌡 Температура: <b>{float(cur_temp):.1f} °C</b>")

            if excess is not None:
                lines.append(f"🔺 <b>Превышение порога: +{float(excess):.1f} °C</b>")

            if action:
                lines.append(f"⚠️ Действие: {html.escape(action)}")

            lines.append(f"⏰ Время: {html.escape(ts_str)}")
        else:
            icon = SEV_ICON.get(sev, "⚠️")
            lines = [
                f"{icon} <b>{html.escape(rule_label)}</b>",
                f"📹 Камера: <b>{html.escape(cam_name)}</b>" + (f" (зона: {html.escape(zone)})" if zone else ""),
                f"⏰ Время: {html.escape(ts_str)}",
            ]
            if action:
                lines.append(f"⚠️ Рекомендация: {html.escape(action)}")

        if status != "new":
            st_text = STATUS_TEXT.get(status, status)
            op_text = f" ({html.escape(operator)})" if operator else ""
            lines.append(f"\n<b>Статус:</b> {st_text}{op_text}")

        return "\n".join(lines)

    def make_keyboard(self, event: dict) -> dict:
        status = event.get("status", "new")
        if status in ("resolved", "dismissed"):
            return {"inline_keyboard": []}

        eid = str(event.get("id") or event.get("event_id") or "0")
        rows = []

        if status in ("new", None):
            rows.append([
                {"text": "Подтвердить", "callback_data": f"st:{eid}:c"},
                {"text": "Ложное", "callback_data": f"st:{eid}:f"},
            ])
            rows.append([
                {"text": "Принял, иду", "callback_data": f"st:{eid}:w"},
            ])
        elif status in ("working", "acknowledged", "confirmed"):
            rows.append([
                {"text": "✔️ Устранено", "callback_data": f"st:{eid}:r"},
                {"text": "✖️ Ложная тревога", "callback_data": f"st:{eid}:f"},
            ])

        # Telegram Bot API запрещает localhost/127.0.0.1 в URL inline-кнопок
        if (
            self.public_url
            and self.public_url.startswith("http")
            and not any(h in self.public_url for h in ("localhost", "127.0.0.1", "0.0.0.0"))
        ):
            rows.append([{"text": "Открыть в дашборде", "url": self.public_url}])

        return {"inline_keyboard": rows}

    def send_alert(self, sub: dict, event: dict, snapshot_path: Optional[str] = None) -> Tuple[str, str]:
        caption = self.format_caption(event)
        kb = self.make_keyboard(event)
        chat_id = sub["chat_id"]

        if snapshot_path and os.path.isfile(snapshot_path):
            with open(snapshot_path, "rb") as f:
                code, raw = post_multipart(
                    f"{self.base}/bot{self.token}/sendPhoto",
                    {
                        "chat_id": chat_id,
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(kb),
                    },
                    {"photo": (os.path.basename(snapshot_path), f.read())},
                )
            d = json.loads(raw.decode("utf-8"))
            if not d.get("ok"):
                raise ApiError(d.get("description", "ошибка отправки фото"), d.get("error_code"))
            return str(d["result"]["message_id"]), "photo"

        # Без фото — обычным сообщением
        res = self.api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": caption,
                "parse_mode": "HTML",
                "reply_markup": kb,
            },
        )
        return str(res["message_id"]), "text"

    def update_alert(self, delivery: dict, event: dict) -> None:
        chat_id = delivery["chat_id"]
        msg_id = int(delivery["message_id"])
        caption = self.format_caption(event)
        kb = self.make_keyboard(event)

        try:
            if delivery.get("kind") == "photo":
                self.api(
                    "editMessageCaption",
                    {
                        "chat_id": chat_id,
                        "message_id": msg_id,
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_markup": kb,
                    },
                )
            else:
                self.api(
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": msg_id,
                        "text": caption,
                        "parse_mode": "HTML",
                        "reply_markup": kb,
                    },
                )
        except ApiError as e:
            if "not modified" not in str(e).lower():
                print(f"[Telegram] Ошибка обновления сообщения: {e}")
