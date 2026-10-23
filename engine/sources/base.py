"""
Базовые классы для источников видеопотоков CV Engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generator, Optional, Tuple
import numpy as np


class BaseVideoSource(ABC):
    """Абстрактный класс источника видеопотока."""

    def __init__(self, fps: float = 25.0, realtime: bool = True) -> None:
        self.fps = fps
        self.realtime = realtime
        self._stop: bool = False

    def stop(self) -> None:
        """Остановка генерации кадров."""
        self._stop = True

    @abstractmethod
    def __iter__(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        """
        Итератор кадров.
        Возвращает кортежи (frame_bgr: np.ndarray, timestamp: float).
        """
        pass
