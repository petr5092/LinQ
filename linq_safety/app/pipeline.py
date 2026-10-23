"""Конвейер одной камеры: кадр -> детектор -> трекер -> правила -> событие."""
import io
import os
import threading
import time

from PIL import Image, ImageDraw

from . import config
from .engine import Engine
from .rules import Context
from .tracker import Tracker


def annotate(img, tracks, dets, zones, hot):
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im, "RGBA")
    for z in zones:
        d.polygon(z["poly"], fill=(242, 183, 5, 45), outline=(242, 183, 5, 255))
    for x in dets:
        if x.cls != "person":
            d.rectangle(x.box, outline=(220, 60, 60) if x.cls.startswith("no_") else (70, 150, 255), width=1)
    for tr in tracks:
        col = (220, 40, 40, 255) if tr.id in hot else (60, 200, 110, 255)
        d.rectangle(tr.box, outline=col, width=3 if tr.id in hot else 2)
        d.text((tr.box[0] + 3, tr.box[1] + 2), f"#{tr.id}", fill=col)
    return im


def jpeg(im, q=80):
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=q)
    return buf.getvalue()


class CameraWorker(threading.Thread):
    def __init__(self, name, source, detector, store, hub, zones):
        super().__init__(daemon=True, name=f"cam-{name}")
        self.cam, self.source, self.detector = name, source, detector
        self.store, self.hub, self.zones = store, hub, zones
        self.tracker, self.engine = Tracker(), Engine()
        self.fps_ema = self.det_ms = self.lat_ms = 0.0
        self.frames, self._last = 0, None
        os.makedirs(config.SNAP_DIR, exist_ok=True)

    def run(self):
        for frame in self.source:
            self.process_frame(frame)

    def stop(self):
        self.source.stop()

    def _zones_px(self, shape):
        h, w = shape[:2]
        return [{"name": z["name"], "poly": [(x * w, y * h) for x, y in z["points"]]}
                for z in self.zones.get(self.cam)]

    def process_frame(self, frame):
        t0 = time.perf_counter()
        dets = self.detector.detect(frame)
        det_ms = (time.perf_counter() - t0) * 1e3
        tracks = self.tracker.update([d for d in dets if d.cls == "person"], frame.t)
        zones = self._zones_px(frame.img.shape)
        fired = self.engine.process(Context(frame.t, frame.img.shape[:2], tracks, dets, zones))
        im = annotate(frame.img, tracks, dets, zones, self.engine.active_tracks)
        events = [self._emit(c, rule, frame, im) for c, rule in fired]
        self.hub.set_frame(self.cam, jpeg(im, 75))
        now = time.perf_counter()
        self.frames += 1
        if self._last:
            inst = 1.0 / max(1e-6, now - self._last)
            self.fps_ema = inst if not self.fps_ema else 0.9 * self.fps_ema + 0.1 * inst
        self._last = now
        self.det_ms = det_ms if not self.det_ms else 0.9 * self.det_ms + 0.1 * det_ms
        self.lat_ms = (now - frame.wall) * 1e3
        self.hub.perf[self.cam] = {"fps": round(self.fps_ema, 1), "detect_ms": round(self.det_ms, 1),
                                   "latency_ms": round(self.lat_ms, 1), "frames": self.frames,
                                   "stages": {k: round(v, 1) for k, v in self.detector.last.items()}}
        return events

    def _emit(self, c, rule, frame, annotated):
        ts = time.time()
        snap = f"{int(ts)}_{self.cam}_{c.type}_{c.track_id}.jpg"
        with open(os.path.join(config.SNAP_DIR, snap), "wb") as f:
            f.write(jpeg(annotated, 88))
        ev = {"ts": ts, "camera": self.cam, "type": c.type, "label": rule.label, "severity": rule.severity,
              "zone": c.zone, "track_id": c.track_id, "status": "new", "snapshot": snap,
              "latency_ms": round((time.perf_counter() - frame.wall) * 1e3, 1)}
        ev["id"] = self.store.add(ev)
        self.hub.publish({"kind": "event", "event": ev})
        return ev
