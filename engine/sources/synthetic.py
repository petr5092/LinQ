"""
Синтетический генератор видеопотока с воспроизведением типовых нарушений ТБ.
Позволяет проводить полное тестирование без подключения физических камер и моделей.
"""

from __future__ import annotations

import time
from typing import Generator, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw

from engine.sources.base import BaseVideoSource

DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 360
SCENARIO_PERIOD = 60.0
DEFAULT_ZONE_POINTS = [[0.62, 0.55], [0.95, 0.55], [0.95, 0.95], [0.62, 0.95]]


def _interpolate(t: float, pts: List[Tuple[float, float]]) -> float:
    """Линейная интерполяция по ключевым точкам [(t, value), ...]."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return pts[-1][1]


def _scenario_actors(t: float) -> List[Tuple[float, float, float, bool, bool, bool]]:
    """
    Сценарий движения работников (60 сек цикл):
    Возвращает список актеров: (cx, foot_y, lying_ratio, helmet, vest, phone)
    """
    actors = []
    # 1. Постоянный рабочий, идущий по проходу в СИЗ
    actors.append((40 + (t % 20) / 20 * 400, 165, 0.0, True, True, False))

    # 2. Рабочий заходит в опасную зону погрузчика (t = 6..21)
    if 6.0 <= t <= 21.0:
        cx = _interpolate(t, [(6.0, 200.0), (10.0, 480.0), (17.0, 480.0), (21.0, 200.0)])
        actors.append((cx, 280.0, 0.0, True, True, False))

    # 3. Рабочий без защитной каски (t = 24..34)
    if 24.0 <= t <= 34.0:
        actors.append((120.0, 250.0, 0.0, False, True, False))

    # 4. Рабочий использует телефон на ходу (t = 38..44)
    if 38.0 <= t <= 44.0:
        actors.append((300.0, 240.0, 0.0, True, True, True))

    # 5. Падение рабочего и неподвижность (t = 46..60)
    if 46.0 <= t < 60.0:
        lie = _interpolate(t, [(48.0, 0.0), (49.0, 1.0)])
        actors.append((250.0, 300.0, lie, True, True, False))

    return actors


def render_scene(t: float, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> np.ndarray:
    """Отрисовка 2D-сцены цеха в RGB формате."""
    im = Image.new("RGB", (width, height), (150, 158, 164))
    draw = ImageDraw.Draw(im)

    # Задняя стена
    draw.rectangle((0, 0, width, int(height * 0.33)), fill=(104, 114, 122))
    for x in range(0, width, 80):
        draw.line((x, 0, x, int(height * 0.33)), fill=(92, 102, 110))

    # Линии на полу цеха
    for y in range(int(height * 0.36), height, 40):
        draw.line((0, y, width, y), fill=(138, 146, 152))

    # Опасная зона со специальной желто-черной разметкой
    zx0 = int(DEFAULT_ZONE_POINTS[0][0] * width)
    zy0 = int(DEFAULT_ZONE_POINTS[0][1] * height)
    zx1 = int(DEFAULT_ZONE_POINTS[2][0] * width)
    zy1 = int(DEFAULT_ZONE_POINTS[2][1] * height)

    draw.rectangle((zx0, zy0, zx1, zy1), outline=(236, 190, 20), width=4)
    for k in range(0, zx1 - zx0, 24):
        draw.line((zx0 + k, zy0, min(zx0 + k + 14, zx1), zy0), fill=(30, 36, 44), width=4)

    # Отрисовка фигурок работников
    for cx, fy, lie, helmet, vest, phone in sorted(_scenario_actors(t), key=lambda a: a[1]):
        w = 36.0 + 74.0 * lie
        h = 110.0 - 74.0 * lie
        x1, y1 = cx - w / 2.0, fy - h
        x2, y2 = cx + w / 2.0, fy

        # Тело (комбинезон)
        draw.rectangle((x1, y1 + 26.0 * (1.0 - lie), x2, y2), fill=(70, 96, 128))

        # Сигнальный жилет со светоотражающими полосами
        if vest and lie < 0.5:
            draw.rectangle((x1 + 2, y1 + 34, x2 - 2, y1 + 68), fill=(240, 120, 20))
            draw.line((x1 + 2, y1 + 46, x2 - 2, y1 + 46), fill=(235, 235, 220), width=3)

        # Голова
        hx = cx + 45.0 * lie
        hy = fy - (97.0 - 79.0 * lie)
        draw.ellipse((hx - 13, hy - 13, hx + 13, hy + 13), fill=(226, 184, 150))

        # Защитная каска
        if helmet:
            draw.pieslice((hx - 15, hy - 17, hx + 15, hy + 13), 180, 360, fill=(250, 214, 40))

        # Телефон возле уха
        if phone:
            draw.rectangle((cx + 8, fy - 70, cx + 20, fy - 52), fill=(20, 24, 30))

    # Преобразуем в BGR формат для OpenCV
    rgb_arr = np.asarray(im)
    return cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)


class SyntheticSource(BaseVideoSource):
    """Синтетический генератор видеокадров с симуляцией нарушений."""

    def __init__(
        self,
        fps: float = 10.0,
        phase: float = 0.0,
        realtime: bool = True,
        max_frames: Optional[int] = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> None:
        super().__init__(fps=fps, realtime=realtime)
        self.phase = phase
        self.max_frames = max_frames
        self.width = width
        self.height = height

    def __iter__(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        i = 0
        t0 = time.perf_counter()
        epoch_start = time.time()
        while not self._stop and (self.max_frames is None or i < self.max_frames):
            sim_t = i / self.fps
            frame_bgr = render_scene((sim_t + self.phase) % SCENARIO_PERIOD, self.width, self.height)
            now = epoch_start + sim_t
            yield frame_bgr, now

            i += 1
            if self.realtime:
                target_time = t0 + i / self.fps
                delay = target_time - time.perf_counter()
                if delay > 0:
                    self.wait(delay)
