"""
Базовые классы для источников видеопотоков CV Engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import math
from typing import Generator, Optional, Tuple
import numpy as np


class BaseVideoSource(ABC):
    """Абстрактный класс источника видеопотока."""

    def __init__(self, fps: float = 25.0, realtime: bool = True) -> None:
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Source FPS must be finite and positive")
        self.fps = fps
        self.realtime = realtime
        self._stop: bool = False
        self.stop_event = None
        # Incremented before the first frame after a seek/reconnect. Consumers
        # must reset temporal state at a discontinuity, not count it as evidence.
        self.sequence_id: int = 0

    def stop(self) -> None:
        """Остановка генерации кадров."""
        self._stop = True

    def is_stopped(self) -> bool:
        return self._stop or (self.stop_event is not None and self.stop_event.is_set())

    def wait(self, seconds: float) -> None:
        if self.stop_event is not None:
            self.stop_event.wait(seconds)
        else:
            import time
            time.sleep(seconds)

    @abstractmethod
    def __iter__(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        """
        Итератор кадров.
        Возвращает кортежи (frame_bgr: np.ndarray, timestamp: float).
        """
        pass
