"""Telegram-бот на long polling (webhook и публичный адрес не нужны).

Чат подключается сам: как только бота добавили в группу или канал, Telegram присылает
my_chat_member, и мы фиксируем чат. В личке подключение — команда /start.
"""
import html
import json
import os
import re
import time

from . import netio
from .core import SEV, STATUS_TEXT, alert_lines, log, status_line
from .netio import ApiError

LEVELS = {"all": "low", "low": "low", "medium": "medium", "high": "high", "critical": "critical"}
CODE = {"c": "confirmed", "f": "false", "w": "forwarded"}


class Telegram:
    channel = "telegram"

    def __init__(self, token, core, base="https://api.telegram.org"):
        self.token, self.core, self.base = token, core, base.rstrip("/")
        self.username, self.status, self.error, self._stop = None, "starting", None, False

    def stop(self):
        self._stop = True

    # --- низкий уровень
    def api(self, method, payload=None, timeout=40):
        code, raw = netio.post_json(f"{self.base}/bot{self.token}/{method}", payload or {}, timeout)
        try:
            d = json.loads(raw)
        except ValueError:
            raise ApiError(f"{method}: HTTP {code}", code)
        if not d.get("ok"):
            raise ApiError(d.get("description", "ошибка API"), d.get("error_code"),
                           (d.get("parameters") or {}).get("retry_after"))
        return d["result"]

    def info(self):
        u = self.username
        return {"configured": True, "status": self.status, "error": self.error, "username": u,
                "links": {"group": f"https://t.me/{u}?startgroup=linq" if u else None,
                          "channel": f"https://t.me/{u}?startchannel=linq&admin=post_messages" if u else None,
                          "private": f"https://t.me/{u}?start=linq" if u else None}}

    def is_gone(self, e):
        m = str(e).lower()
        return e.code == 403 or "chat not found" in m or "kicked" in m or "deactivated" in m

    # --- жизненный цикл
    def run(self):
        offset = None
        while not self._stop:
            try:
                if self.status != "online":
                    me = self.api("getMe")
                    self.username = me["username"]
                    self.api("deleteWebhook")
                    self.api("setMyCommands", {"commands": [
                        {"command": "start", "description": "Подключить этот чат к уведомлениям"},
                        {"command": "status", "description": "Состояние и сводка за сутки"},
                        {"command": "level", "description": "Порог важности: all, medium, high, critical"},
                        {"command": "stop", "description": "Отключить уведомления"}]})
                    self.status, self.error = "online", None
                    log(f"telegram: бот @{self.username} запущен")
                params = {"timeout": 25, "allowed_updates": ["message", "my_chat_member", "callback_query"]}
                if offset:
                    params["offset"] = offset
                for upd in self.api("getUpdates", params, timeout=40):
                    offset = upd["update_id"] + 1
                    try:
                        self.handle(upd)
                    except ApiError as e:
                        log("telegram: ошибка обработки:", type(e).__name__)
            except ApiError as e:
                self.status, self.error = "error", str(e)
                if e.code == 401:
                    log("telegram: неверный токен, останавливаюсь")
                    return
                time.sleep(5)

    # --- входящие
    def handle(self, upd):
        if "my_chat_member" in upd:
            return self.on_membership(upd["my_chat_member"])
        if "callback_query" in upd:
            return self.on_callback(upd["callback_query"])
        m = upd.get("message") or {}
        if "migrate_to_chat_id" in m:
            return self.core.store.move_chat(self.channel, m["chat"]["id"], m["migrate_to_chat_id"])
        text = (m.get("text") or "").strip()
        if text.startswith("/"):
            cmd, _, arg = text.partition(" ")
            cmd = cmd.split("@")[0].lower()
            if "@" in text.split(" ")[0] and text.split(" ")[0].split("@")[1].lower() != (self.username or "").lower():
                return                                             # команда адресована другому боту
            self.on_command(m, cmd, arg.strip())

    def title(self, chat):
        return chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])) \
            or chat.get("username") or str(chat["id"])

    def who(self, user):
        return "@" + user["username"] if user.get("username") else user.get("first_name", "оператор")

    def on_membership(self, m):
        chat, new = m["chat"], m["new_chat_member"]["status"]
        if chat["type"] == "private":
            if new == "kicked":
                self.core.unregister(self.channel, chat["id"])
            return
        if new in ("member", "administrator"):
            self.core.register(self.channel, chat["id"], self.title(chat), chat["type"], self.who(m["from"]))
            self.say(chat["id"], "Подключился. Сюда будут приходить нарушения с кадром и кнопками "
                                 "«Подтвердить» / «Ложное» / «Принял, иду».\n"
                                 "Порог важности: /level, сводка: /status, отключить: /stop.")
        elif new in ("left", "kicked"):
            self.core.unregister(self.channel, chat["id"])

    def on_command(self, m, cmd, arg):
        chat = m["chat"]
        cid = chat["id"]
        if cmd in ("/start", "/connect"):
            self.core.register(self.channel, cid, self.title(chat), chat["type"], self.who(m.get("from", {})))
            self.say(cid, "Уведомления подключены. Сюда придут нарушения с кадром и кнопками действий.\n"
                          "Порог важности: /level, сводка: /status, отключить: /stop.")
        elif cmd == "/stop":
            self.core.unregister(self.channel, cid)
            self.say(cid, "Уведомления отключены. Вернуть: /start.")
        elif cmd == "/status":
            sub = self.core.store.get_sub(self.channel, cid)
            state = "подключён" if sub and sub["active"] else "не подключён (/start)"
            lvl = sub["min_severity"] if sub else "—"
            self.say(cid, f"Чат {state}. Порог: {lvl}.\n{self.core.summary()}")
        elif cmd == "/level":
            if arg.lower() in LEVELS and self.core.store.get_sub(self.channel, cid):
                sub = self.core.store.get_sub(self.channel, cid)
                self.core.store.update_sub(sub["id"], min_severity=LEVELS[arg.lower()])
                self.say(cid, f"Порог: {LEVELS[arg.lower()]}. Ниже этого уровня оповещения в чат не идут.")
            else:
                self.say(cid, "Использование: /level all | medium | high | critical (сначала /start).")
        elif cmd == "/help":
            self.say(cid, "/start — подключить чат\n/status — сводка\n/level — порог важности\n/stop — отключить")

    def on_callback(self, cq):
        mt = re.fullmatch(r"st:(\d+):([cfw])", cq.get("data", ""))
        if not mt:
            return self.api("answerCallbackQuery", {"callback_query_id": cq["id"]})
        ev = self.core.set_status(int(mt.group(1)), CODE[mt.group(2)], self.who(cq["from"]))
        self.api("answerCallbackQuery", {"callback_query_id": cq["id"],
                                         "text": STATUS_TEXT[ev["status"]] if ev else "Событие не найдено"})

    # --- исходящие
    def say(self, chat_id, text):
        try:
            self.api("sendMessage", {"chat_id": chat_id, "text": text})
        except ApiError as e:
            log("telegram: не отправить сообщение:", type(e).__name__)

    def caption(self, ev):
        a, b, c = alert_lines(ev)
        s = status_line(ev)
        return f"<b>{html.escape(a)}</b>\n{html.escape(b)}\n{html.escape(c)}" + (f"\n\n{html.escape(s)}" if s else "")

    def keyboard(self, ev):
        if ev["id"] == 0 or ev.get("status") != "new":
            return {"inline_keyboard": []}
        i = ev["id"]
        rows = [[{"text": "Подтвердить", "callback_data": f"st:{i}:c"}, {"text": "Ложное", "callback_data": f"st:{i}:f"}],
                [{"text": "Принял, иду", "callback_data": f"st:{i}:w"}]]
        if (
            self.core.public_url
            and self.core.public_url.startswith("http")
            and not any(h in self.core.public_url for h in ("localhost", "127.0.0.1", "0.0.0.0"))
        ):
            rows.append([{"text": "Открыть в панели", "url": self.core.public_url}])
        return {"inline_keyboard": rows}

    def send_alert(self, sub, ev, snap):
        cap, kb = self.caption(ev), self.keyboard(ev)
        if snap and os.path.isfile(snap):
            with open(snap, "rb") as f:
                code, raw = netio.post_multipart(
                    f"{self.base}/bot{self.token}/sendPhoto",
                    {"chat_id": sub["chat_id"], "caption": cap, "parse_mode": "HTML", "reply_markup": json.dumps(kb)},
                    {"photo": (os.path.basename(snap), f.read())})
            d = json.loads(raw)
            if not d.get("ok"):
                raise ApiError(d.get("description", "ошибка"), d.get("error_code"),
                               (d.get("parameters") or {}).get("retry_after"))
            return d["result"]["message_id"], "photo"
        r = self.api("sendMessage", {"chat_id": sub["chat_id"], "text": cap, "parse_mode": "HTML", "reply_markup": kb})
        return r["message_id"], "text"

    def update_alert(self, delivery, ev):
        common = {"chat_id": delivery["chat_id"], "message_id": int(delivery["message_id"]),
                  "parse_mode": "HTML", "reply_markup": self.keyboard(ev)}
        try:
            if delivery["kind"] == "photo":
                self.api("editMessageCaption", {**common, "caption": self.caption(ev)})
            else:
                self.api("editMessageText", {**common, "text": self.caption(ev)})
        except ApiError as e:
            if "not modified" not in str(e):
                raise
