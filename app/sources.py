"""Источники кадров: синтетическая сцена, папка изображений, видеофайл/RTSP."""
import glob
import os
import time

import numpy as np
from PIL import Image, ImageDraw

from .models import Detection, Frame

W, H = 640, 360
PERIOD = 60.0
DEFAULT_ZONE = [[0.62, 0.55], [0.95, 0.55], [0.95, 0.95], [0.62, 0.95]]   # совпадает с разметкой на полу


def _seg(t, pts):
    """Линейная интерполяция по ключевым точкам [(t, value), ...] с насыщением."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return pts[-1][1]


def _actors(t):
    """Сценарий на 60 секунд: (cx, foot_y, lying 0..1, helmet, vest, phone)."""
    a = []
    a.append((40 + (t % 20) / 20 * 400, 165, 0, True, True, False))                    # идёт по проходу, всё в порядке
    if 6 <= t <= 21:                                                                     # заходит в опасную зону
        cx = _seg(t, [(6, 200), (10, 480), (17, 480), (21, 200)])
        a.append((cx, 280, 0, True, True, False))
    if 24 <= t <= 34:                                                                    # без каски
        a.append((120, 250, 0, False, True, False))
    if 38 <= t <= 44:                                                                    # с телефоном
        a.append((300, 240, 0, True, True, True))
    if 46 <= t < 60:                                                                     # падает и лежит
        a.append((250, 300, _seg(t, [(48, 0), (49, 1)]), True, True, False))
    return a


def _render(t):
    im = Image.new("RGB", (W, H), (150, 158, 164))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 120), fill=(104, 114, 122))
    for x in range(0, W, 80):
        d.line((x, 0, x, 120), fill=(92, 102, 110))
    for y in range(130, H, 40):
        d.line((0, y, W, y), fill=(138, 146, 152))
    zx0, zy0, zx1, zy1 = (DEFAULT_ZONE[0][0] * W, DEFAULT_ZONE[0][1] * H, DEFAULT_ZONE[2][0] * W, DEFAULT_ZONE[2][1] * H)
    d.rectangle((zx0, zy0, zx1, zy1), outline=(236, 190, 20), width=4)
    for k in range(0, int(zx1 - zx0), 24):
        d.line((zx0 + k, zy0, zx0 + k + 14, zy0), fill=(30, 36, 44), width=4)
    gt = []
    for cx, fy, lie, helmet, vest, phone in sorted(_actors(t), key=lambda a: a[1]):
        w, h = 36 + 74 * lie, 110 - 74 * lie
        x1, y1, x2, y2 = cx - w / 2, fy - h, cx + w / 2, fy
        d.rectangle((x1, y1 + 26 * (1 - lie), x2, y2), fill=(70, 96, 128))                # тело
        if vest and lie < .5:
            d.rectangle((x1 + 2, y1 + 34, x2 - 2, y1 + 68), fill=(240, 120, 20))
            d.line((x1 + 2, y1 + 46, x2 - 2, y1 + 46), fill=(235, 235, 220), width=3)
        hx, hy = cx + 45 * lie, fy - (97 - 79 * lie)
        d.ellipse((hx - 13, hy - 13, hx + 13, hy + 13), fill=(226, 184, 150))             # голова
        if helmet:
            d.pieslice((hx - 15, hy - 17, hx + 15, hy + 13), 180, 360, fill=(250, 214, 40))
        if phone:
            d.rectangle((cx + 8, fy - 70, cx + 20, fy - 52), fill=(20, 24, 30))
        D = Detection
        gt.append(D("person", .95, (x1, y1, x2, y2)))
        head = (hx - 13, hy - 13, hx + 13, hy + 13)
        gt.append(D("helmet" if helmet else "no_helmet", .9, (hx - 15, hy - 17, hx + 15, hy + 13) if helmet else head))
        if lie < .5:
            torso = (x1, y1 + 34, x2, y1 + 68)
            gt.append(D("vest" if vest else "no_vest", .9, torso))
        if phone:
            gt.append(D("phone", .8, (cx + 8, fy - 70, cx + 20, fy - 52)))
    return np.asarray(im), gt


class SyntheticSource:
    kind = "synthetic"

    def __init__(self, fps=10, phase=0.0, realtime=True, max_frames=None):
        self.fps, self.phase, self.realtime, self.max_frames = fps, phase, realtime, max_frames
        self._stop = False

    def stop(self):
        self._stop = True

    def __iter__(self):
        i, t0 = 0, time.perf_counter()
        while not self._stop and (self.max_frames is None or i < self.max_frames):
            t = i / self.fps
            img, gt = _render((t + self.phase) % PERIOD)
            yield Frame(img, t, time.perf_counter(), {"gt": gt})
            i += 1
            if self.realtime:
                time.sleep(max(0.0, t0 + i / self.fps - time.perf_counter()))


class ImageFolderSource:
    kind = "images"

    def __init__(self, folder, fps=2.0, realtime=True):
        exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
        self.files = sorted(f for e in exts for f in glob.glob(os.path.join(folder, e)))
        if not self.files:
            raise SystemExit(f"в папке {folder} нет изображений")
        self.fps, self.realtime, self._stop = fps, realtime, False

    def stop(self):
        self._stop = True

    def __iter__(self):
        i, t0 = 0, time.perf_counter()
        while not self._stop:
            img = np.asarray(Image.open(self.files[i % len(self.files)]).convert("RGB"))
            yield Frame(img, i / self.fps, time.perf_counter())
            i += 1
            if self.realtime:
                time.sleep(max(0.0, t0 + i / self.fps - time.perf_counter()))


class VideoSource:
    """Видеофайл (по кругу) или RTSP. Нужен opencv-python-headless."""
    kind = "video"

    def __init__(self, url, realtime=True):
        try:
            import cv2
        except ImportError as e:
            raise SystemExit("Для видео и RTSP установите: pip install opencv-python-headless") from e
        self.cv2, self.url, self.realtime, self._stop = cv2, url, realtime, False
        self.is_stream = "://" in url

    def stop(self):
        self._stop = True

    def __iter__(self):
        cv2, t0, n = self.cv2, time.perf_counter(), 0
        cap = cv2.VideoCapture(self.url)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        while not self._stop:
            ok, bgr = cap.read()
            if not ok:
                cap.release()
                time.sleep(1.0 if self.is_stream else 0)      # поток оборвался — переподключаемся
                cap = cv2.VideoCapture(self.url)
                continue
            now = time.perf_counter()
            yield Frame(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), (now - t0) if self.is_stream else n / fps, now)
            n += 1
            if self.realtime and not self.is_stream:
                time.sleep(max(0.0, t0 + n / fps - time.perf_counter()))
        cap.release()


def open_source(spec, realtime=True):
    """'synthetic' | 'synthetic:30' (сдвиг сценария, сек) | 'demo' | папка | файл | rtsp://..."""
    if spec.startswith("synthetic"):
        phase = float(spec.split(":")[1]) if ":" in spec else 0.0
        return SyntheticSource(phase=phase, realtime=realtime)
    if spec in ("demo", "demo_video", "demo.mp4"):
        for candidate in ("construction_safety.mp4", "16106604-uhd_3840_2160_30fps.mp4"):
            demo_path = os.path.join(config.ROOT, "storage", "demo_videos", candidate)
            if os.path.isfile(demo_path):
                return VideoSource(demo_path, realtime=realtime)
    if os.path.isdir(spec):
        return ImageFolderSource(spec, realtime=realtime)
    return VideoSource(spec, realtime=realtime)
