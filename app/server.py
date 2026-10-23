"""HTTP-СЃРµСЂРІРµСЂ РЅР° СЃС‚Р°РЅРґР°СЂС‚РЅРѕР№ Р±РёР±Р»РёРѕС‚РµРєРµ: РІРµР±-РёРЅС‚РµСЂС„РµР№СЃ, REST, SSE, MJPEG."""
import csv
import io
import json
import logging
import os
import queue
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import config
from .enterprise import EnterpriseConfig
from .rules import RULES
from .store import STATUSES

WEB = os.path.join(config.ROOT, "frontend")
APP = {}      # store, hub, zones, cameras, backend вЂ” Р·Р°РїРѕР»РЅСЏРµС‚СЃСЏ РІ serve()
CAMERA_STALE_AFTER_S = 10
CAMERA_START_TIMEOUT_S = 15
http_logger = logging.getLogger("linq.http")
_QUIET_PATHS = ("/api/frame/", "/api/perf", "/api/cameras", "/api/live", "/api/stream/")


def camera_statuses(hub, cameras, now=None):
    now = time.time() if now is None else now
    states = hub.get_camera_states()
    result = []
    for camera in cameras:
        state = states.get(camera["id"], {})
        status = state.get("status", "starting")
        last_frame_ts = state.get("last_frame_ts")
        age = max(0, now - last_frame_ts) if last_frame_ts is not None else None
        started_ts = state.get("started_ts", now)
        if status not in ("error", "stopped", "stopping"):
            if age is not None and age > CAMERA_STALE_AFTER_S:
                status = "offline"
            elif age is None and now - started_ts > CAMERA_START_TIMEOUT_S:
                status = "offline"
        result.append({
            "id": camera["id"],
            "status": status,
            "last_frame_ts": last_frame_ts,
            "last_frame_age_s": round(age, 1) if age is not None else None,
            "frames": state.get("frames", 0),
            "error": state.get("error"),
        })
    return result


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def log_request(self, code="-", size="-"):
        path = urlparse(self.path).path
        if (str(code).startswith("4") or str(code).startswith("5") or self.command != "GET"
                or not path.startswith(_QUIET_PATHS)):
            http_logger.info("client=%s method=%s path=%s status=%s bytes=%s",
                             self.client_address[0], self.command, path, code, size)

    # --- РІСЃРїРѕРјРѕРіР°С‚РµР»СЊРЅРѕРµ
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def _filters(self, q):
        g = lambda k: (q.get(k) or [None])[0]
        return dict(type=g("type"), camera=g("camera"), zone=g("zone"), status=g("status"),
                    workshop=g("workshop"), shift=g("shift"), since=g("since"), until=g("until"),
                    limit=g("limit") or 200)

    # --- GET
    def do_GET(self):
        u = urlparse(self.path)
        q, p = parse_qs(u.query), u.path
        try:
            if p in ("/", "/index.html"):
                with open(os.path.join(WEB, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if p == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if p == "/api/meta":
                return self._send(200, {
                    "backend": APP["backend"],
                    "cameras": [{"id": c["id"], "workshop": c.get("workshop", "РќРµ РЅР°Р·РЅР°С‡РµРЅ")}
                                for c in APP["cameras"]],
                    "workshops": sorted(set(APP["enterprise"].camera_workshops.values())
                                        | {c.get("workshop", "РќРµ РЅР°Р·РЅР°С‡РµРЅ") for c in APP["cameras"]}),
                    "shifts": [s["name"] for s in APP["enterprise"].shifts],
                    "statuses": STATUSES,
                    "types": {k: {"label": r.label, "severity": r.severity} for k, r in RULES.items()}})
            if p == "/api/cameras":
                return self._send(200, camera_statuses(APP["hub"], APP["cameras"]))
            if p == "/api/events":
                return self._send(200, APP["store"].query(**self._filters(q)))
            m = re.fullmatch(r"/api/events/(\d+)/history", p)
            if m:
                eid = int(m.group(1))
                if APP["store"].get(eid) is None:
                    return self._send(404, {"error": "СЃРѕР±С‹С‚РёРµ РЅРµ РЅР°Р№РґРµРЅРѕ"})
                return self._send(200, APP["store"].history(eid))
            if p == "/api/events.csv":
                rows = APP["store"].query(**{**self._filters(q), "limit": 100000})
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(["id", "РІСЂРµРјСЏ", "РєР°РјРµСЂР°", "СѓС‡Р°СЃС‚РѕРє", "СЃРјРµРЅР°", "РґР°С‚Р°_СЃРјРµРЅС‹", "Р·РѕРЅР°",
                            "С‚РёРї", "РІР°Р¶РЅРѕСЃС‚СЊ", "СЃС‚Р°С‚СѓСЃ", "РєС‚Рѕ_РѕР±СЂР°Р±РѕС‚Р°Р»", "РІСЂРµРјСЏ_РѕР±СЂР°Р±РѕС‚РєРё",
                            "Р·Р°РґРµСЂР¶РєР°_РјСЃ", "РєР°РґСЂ"])
                import time as _t
                for r in rows:
                    w.writerow([r["id"], _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(r["ts"])), r["camera"],
                                r["workshop"] or "РќРµ РЅР°Р·РЅР°С‡РµРЅ", r["shift"] or "РќРµ РѕРїСЂРµРґРµР»РµРЅР°",
                                r["shift_date"] or "", r["zone"] or "", r["label"], r["severity"], r["status"],
                                r["handled_by"] or "", _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(r["handled_ts"]))
                                if r["handled_ts"] else "", r["latency_ms"], r["snapshot"]])
                return self._send(200, ("\ufeff" + buf.getvalue()).encode("utf-8"), "text/csv; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="events.csv"'})
            if p == "/api/dashboard":
                per = {"24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400}.get((q.get("period") or ["24h"])[0])
                import time as _t
                d = APP["store"].dashboard(since=_t.time() - per if per else None)
                n = APP.get("notifier")
                d["notifications"] = n.store.delivery_stats() if n else {}
                d["perf"] = APP["hub"].perf
                d["cameras"] = camera_statuses(APP["hub"], APP["cameras"])
                return self._send(200, d)
            if p == "/metrics":
                return self._send(200, self._metrics().encode(), "text/plain; version=0.0.4; charset=utf-8")
            if p == "/api/notify":
                n = APP.get("notifier")
                return self._send(200, n.info() if n else {"channels": {}, "subscribers": [], "stats": {}})
            if p == "/api/stats":
                return self._send(200, APP["store"].stats())
            if p == "/api/perf":
                return self._send(200, {"backend": APP["backend"], "cameras": APP["hub"].perf,
                                        "detector": APP["detector"].last,
                                        "camera_statuses": camera_statuses(APP["hub"], APP["cameras"])})
            m = re.fullmatch(r"/api/zones/([\w\-]+)", p)
            if m:
                return self._send(200, APP["zones"].get(m.group(1)))
            if p.startswith("/snaps/"):
                fp = os.path.join(config.SNAP_DIR, os.path.basename(p))
                if os.path.isfile(fp):
                    with open(fp, "rb") as f:
                        return self._send(200, f.read(), "image/jpeg")
                return self._send(404, {"error": "РЅРµС‚ С„Р°Р№Р»Р°"})
            m = re.fullmatch(r"/api/frame/([\w\-]+)\.jpg", p)
            if m:
                data = APP["hub"].frames.get(m.group(1), (0, b""))[1]
                if not data:
                    return self._send(404, {"error": "РєР°РґСЂР° РµС‰С‘ РЅРµС‚"})
                return self._send(200, data, "image/jpeg")
            m = re.fullmatch(r"/api/stream/([\w\-]+)", p)
            if m:
                return self._mjpeg(m.group(1))
            if p == "/api/live":
                return self._sse()
            self._send(404, {"error": "РЅРµ РЅР°Р№РґРµРЅРѕ"})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _metrics(self):
        """Р¤РѕСЂРјР°С‚ Prometheus: РїРѕРґРєР»СЋС‡Р°РµС‚СЃСЏ Рє Grafana Р±РµР· РґРѕСЂР°Р±РѕС‚РѕРє."""
        esc = lambda v: str(v).replace("\\", "\\\\").replace('"', '\\"')
        st, hub, out = APP["store"], APP["hub"], []
        rows = st.query(limit=100000)
        agg = {}
        for r in rows:
            k = (r["type"], r["camera"], r["severity"])
            agg[k] = agg.get(k, 0) + 1
        out.append("# TYPE linq_events_total counter")
        out += [f'linq_events_total{{type="{esc(t)}",camera="{esc(c)}",severity="{esc(v)}"}} {n}' for (t, c, v), n in agg.items()]
        d = st.dashboard()
        out += ["# TYPE linq_events_pending gauge", f"linq_events_pending {d['pending']}",
                "# TYPE linq_events_false_total counter", f"linq_events_false_total {d['by_status'].get('false', 0)}"]
        if d["reaction_s"]["avg"] is not None:
            out += ["# TYPE linq_reaction_seconds_avg gauge", f"linq_reaction_seconds_avg {d['reaction_s']['avg']:.2f}"]
        out.append("# TYPE linq_camera_online gauge")
        out += [f'linq_camera_online{{camera="{esc(c["id"])}"}} {int(c["status"] == "online")}'
                for c in camera_statuses(hub, APP["cameras"])]
        for cam, p in hub.perf.items():
            out += [f'linq_camera_fps{{camera="{esc(cam)}"}} {p["fps"]}',
                    f'linq_camera_detect_ms{{camera="{esc(cam)}"}} {p["detect_ms"]}',
                    f'linq_camera_latency_ms{{camera="{esc(cam)}"}} {p["latency_ms"]}']
        n = APP.get("notifier")
        if n:
            for ch, v in n.store.delivery_stats().items():
                out += [f'linq_notifications_total{{channel="{ch}",result="ok"}} {v["ok"]}',
                        f'linq_notifications_total{{channel="{ch}",result="failed"}} {v["failed"]}']
        return "\n".join(out) + "\n"

    def _mjpeg(self, cam):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        seq = 0
        try:
            while True:
                seq, data = APP["hub"].wait_frame(cam, seq)
                if not data:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(data)
                                 + data + b"\r\n")
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        q = APP["hub"].subscribe()
        try:
            while True:
                try:
                    msg = q.get(timeout=15)
                    self.wfile.write(b"data: " + json.dumps(msg, ensure_ascii=False).encode() + b"\n\n")
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            APP["hub"].unsubscribe(q)

    # --- POST
    def do_POST(self):
        p = urlparse(self.path).path
        m = re.fullmatch(r"/api/events/(\d+)/status", p)
        if m:
            body = self._body()
            ev = APP["store"].set_status(int(m.group(1)), body.get("status"), body.get("by"))
            if not ev:
                return self._send(400, {"error": "РЅРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ РёР»Рё СЃРѕР±С‹С‚РёРµ"})
            APP["hub"].publish({"kind": "status", "event": ev})
            return self._send(200, ev)
        n = APP.get("notifier")
        if p == "/api/notify/test" and n:
            return self._send(200, {"sent_to": n.send_test(self._body().get("id"))})
        m = re.fullmatch(r"/api/notify/subscribers/(\d+)", p)
        if m and n:
            sid, b = int(m.group(1)), self._body()
            if b.get("delete"):
                n.store.delete_sub(sid)
            else:
                if b.get("min_severity") in ("low", "medium", "high", "critical") or "active" in b:
                    n.store.update_sub(sid, **{k: b[k] for k in ("min_severity", "active") if k in b})
            return self._send(200, {"ok": True})
        m = re.fullmatch(r"/api/zones/([\w\-]+)", p)
        if m:
            zones = APP["zones"].set(m.group(1), self._body().get("zones", []))
            return self._send(200, zones)
        self._send(404, {"error": "РЅРµ РЅР°Р№РґРµРЅРѕ"})


def serve(port, store, hub, zones, cameras, detector, host="127.0.0.1", notifier=None, enterprise=None):
    APP.update(notifier=notifier, store=store, hub=hub, zones=zones, cameras=cameras, detector=detector,
               backend=detector.name, enterprise=enterprise or EnterpriseConfig())
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv
