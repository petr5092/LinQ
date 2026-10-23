"""Бот сообщества VK на Bots Long Poll API.

Нужно: токен сообщества с правами «сообщения» и «фотографии», включённые сообщения сообщества,
Long Poll API (события message_new, message_event), «Разрешать добавлять сообщество в беседы».
Беседа подключается, когда сообщество добавляют в неё (событие chat_invite_user) или командой /start.
Чтобы бот видел команды в беседе, назначьте сообщество администратором беседы.
"""
import json
import time
import urllib.parse

from . import netio
from .core import STATUS_TEXT, alert_lines, log, status_line
from .netio import ApiError

V = "5.199"
LEVELS = {"all": "low", "low": "low", "medium": "medium", "high": "high", "critical": "critical"}
CHAT_BASE = 2_000_000_000


class VK:
    channel = "vk"

    def __init__(self, token, core, group_id=None, base="https://api.vk.com/method/"):
        self.token, self.core, self.base = token, core, base if base.endswith("/") else base + "/"
        self.group_id = int(group_id) if group_id else None
        self.name = None
        self.status, self.error, self._stop, self._rid = "starting", None, False, int(time.time() * 1000)

    def stop(self):
        self._stop = True

    def api(self, method, **params):
        params.update(access_token=self.token, v=V)
        code, raw = netio.post_form(self.base + method, params, 40)
        try:
            d = json.loads(raw)
        except ValueError:
            raise ApiError(f"{method}: HTTP {code}", code)
        if "error" in d:
            e = d["error"]
            raise ApiError(e.get("error_msg", "ошибка VK"), e.get("error_code"))
        return d["response"]

    def info(self):
        gid = self.group_id
        return {"configured": True, "status": self.status, "error": self.error, "username": self.name,
                "links": {"group": f"https://vk.com/club{gid}" if gid else None, "channel": None,
                          "private": f"https://vk.me/club{gid}" if gid else None}}

    def is_gone(self, e):
        return e.code in (7, 15, 917, 922, 946)       # нет прав, доступ запрещён, бота исключили из беседы

    def rid(self):
        self._rid += 1
        return self._rid

    # --- жизненный цикл
    def run(self):
        ts = server = key = None
        while not self._stop:
            try:
                if not server:
                    if not self.group_id:
                        g = self.api("groups.getById")["groups"][0]
                        self.group_id, self.name = g["id"], g.get("name")
                    lp = self.api("groups.getLongPollServer", group_id=self.group_id)
                    server, key, ts = lp["server"], lp["key"], lp["ts"]
                    self.status, self.error = "online", None
                    log(f"vk: бот сообщества {self.group_id} запущен")
                url = f"{server}?{urllib.parse.urlencode({'act': 'a_check', 'key': key, 'ts': ts, 'wait': 25})}"
                code, raw = netio.request(url, timeout=40)
                d = json.loads(raw)
                if "failed" in d:
                    if d["failed"] == 1:
                        ts = d["ts"]
                    else:
                        server = None                       # ключ устарел — получаем заново
                    continue
                ts = d["ts"]
                for u in d.get("updates", []):
                    try:
                        self.handle(u)
                    except ApiError as e:
                        log("vk: ошибка обработки:", e)
            except (ApiError, ValueError) as e:
                self.status, self.error, server = "error", str(e), None
                time.sleep(5)

    # --- входящие
    def handle(self, u):
        if u["type"] == "message_new":
            m = u["object"]["message"]
            act = m.get("action") or {}
            peer = m["peer_id"]
            if act.get("type") == "chat_invite_user" and act.get("member_id") == -self.group_id:
                self.core.register(self.channel, peer, f"Беседа {peer - CHAT_BASE}", "chat", f"id{m['from_id']}")
                return self.say(peer, "Подключился. Сюда будут приходить нарушения с кадром и кнопками действий.\n"
                                      "Чтобы я видел команды /status, /level, /stop, сделайте сообщество администратором беседы.")
            if act.get("type") == "chat_kick_user" and act.get("member_id") == -self.group_id:
                return self.core.unregister(self.channel, peer)
            self.on_command(m, peer, (m.get("text") or "").strip())
        elif u["type"] == "message_event":
            self.on_callback(u["object"])

    def on_command(self, m, peer, text):
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower().lstrip("/").split("@")[0]
        if cmd in ("start", "начать", "connect"):
            title = f"Беседа {peer - CHAT_BASE}" if peer > CHAT_BASE else f"Диалог id{m['from_id']}"
            self.core.register(self.channel, peer, title, "chat" if peer > CHAT_BASE else "private", f"id{m['from_id']}")
            self.say(peer, "Уведомления подключены. Порог важности: /level, сводка: /status, отключить: /stop.")
        elif cmd == "stop":
            self.core.unregister(self.channel, peer)
            self.say(peer, "Уведомления отключены. Вернуть: /start.")
        elif cmd == "status":
            sub = self.core.store.get_sub(self.channel, peer)
            self.say(peer, f"Чат {'подключён' if sub and sub['active'] else 'не подключён (/start)'}. "
                           f"Порог: {sub['min_severity'] if sub else '—'}.\n{self.core.summary()}")
        elif cmd == "level":
            sub = self.core.store.get_sub(self.channel, peer)
            if sub and arg.lower() in LEVELS:
                self.core.store.update_sub(sub["id"], min_severity=LEVELS[arg.lower()])
                self.say(peer, f"Порог: {LEVELS[arg.lower()]}.")
            else:
                self.say(peer, "Использование: /level all | medium | high | critical (сначала /start).")

    def on_callback(self, o):
        p = o.get("payload") or {}
        ev = self.core.set_status(int(p["id"]), p["s"], f"id{o['user_id']}") if "id" in p else None
        text = STATUS_TEXT[ev["status"]] if ev else "Событие не найдено"
        self.api("messages.sendMessageEventAnswer", event_id=o["event_id"], user_id=o["user_id"], peer_id=o["peer_id"],
                 event_data=json.dumps({"type": "show_snackbar", "text": text}, ensure_ascii=False))

    # --- исходящие
    def say(self, peer, text):
        try:
            self.api("messages.send", peer_id=peer, message=text, random_id=self.rid())
        except ApiError as e:
            log("vk: не отправить сообщение:", e)

    def keyboard(self, ev):
        if ev["id"] == 0 or ev.get("status") != "new":
            return None
        def btn(label, status, color):
            return {"action": {"type": "callback", "label": label,
                               "payload": json.dumps({"id": ev["id"], "s": status})}, "color": color}
        return json.dumps({"inline": True, "buttons": [[btn("Подтвердить", "confirmed", "positive"),
                                                        btn("Ложное", "false", "negative")],
                                                       [btn("Принял, иду", "forwarded", "primary")]]})

    def upload(self, peer, snap):
        srv = self.api("photos.getMessagesUploadServer", peer_id=peer)["upload_url"]
        with open(snap, "rb") as f:
            code, raw = netio.post_multipart(srv, {}, {"photo": ("alert.jpg", f.read())})
        r = json.loads(raw)
        p = self.api("photos.saveMessagesPhoto", server=r["server"], photo=r["photo"], hash=r["hash"])[0]
        return f"photo{p['owner_id']}_{p['id']}"

    def send_alert(self, sub, ev, snap):
        peer = int(sub["chat_id"])
        a, b, c = alert_lines(ev)
        text = f"{a}\n{b}\n{c}"
        att = None
        if snap:
            try:
                att = self.upload(peer, snap)
            except (ApiError, OSError, ValueError, KeyError) as e:
                log("vk: фото не загрузилось, отправляю текстом:", e)
        params = {"peer_id": peer, "message": text, "random_id": self.rid()}
        if att:
            params["attachment"] = att
        kb = self.keyboard(ev)
        if kb:
            params["keyboard"] = kb
        r = self.api("messages.send", **params)
        return r if isinstance(r, int) else json.dumps(r), "photo" if att else "text"

    def update_alert(self, delivery, ev):
        pass            # VK не позволяет надёжно править сообщения с фото; статус виден в панели и ответом на кнопку
