"""
Фильтр Калмана для пространственно-временного сглаживания и предсказания движения рамок (ByteTrack).
Вектор состояния: [xc, yc, a, h, vxc, vyc, va, vh], где a = w / h.
"""

from __future__ import annotations

from typing import Tuple
import numpy as np


class KalmanBoxTracker:
    """
    Линейный фильтр Калмана для аппроксимации движения ограничивающего прямоугольника.
    """

    count = 0

    def __init__(self, bbox_xyxy: Tuple[float, float, float, float]) -> None:
        # Вектор состояния 8D: [xc, yc, a, h, vx, vy, va, vh]
        self.state = np.zeros((8, 1), dtype=np.float32)

        # Ковариационная матрица ошибки оценки (P)
        self.P = np.eye(8, dtype=np.float32)
        self.P[4:, 4:] *= 1000.0  # большая неопределенность по начальным скоростям
        self.P *= 10.0

        # Матрица перехода состояния (F)
        self.F = np.eye(8, dtype=np.float32)
        for i in range(4):
            self.F[i, i + 4] = 1.0  # x = x0 + v * dt (dt = 1 кадр)

        # Матрица измерений (H) 4x8: наблюдаем [xc, yc, a, h]
        self.H = np.zeros((4, 8), dtype=np.float32)
        for i in range(4):
            self.H[i, i] = 1.0

        # Ковариация шума процесса (Q)
        self.Q = np.eye(8, dtype=np.float32)
        self.Q[4:, 4:] *= 0.01

        # Ковариация шума измерений (R)
        self.R = np.eye(4, dtype=np.float32) * 1.0

        # Инициализация первого измерения
        z = self._xyxy_to_z(bbox_xyxy)
        self.state[:4] = z

        KalmanBoxTracker.count += 1
        self.id = KalmanBoxTracker.count

    @staticmethod
    def _xyxy_to_z(xyxy: Tuple[float, float, float, float]) -> np.ndarray:
        """Преобразует [x1, y1, x2, y2] в [xc, yc, a, h] (a = w / h)."""
        w = max(1e-4, xyxy[2] - xyxy[0])
        h = max(1e-4, xyxy[3] - xyxy[1])
        xc = xyxy[0] + w / 2.0
        yc = xyxy[1] + h / 2.0
        a = w / h
        return np.array([[xc], [yc], [a], [h]], dtype=np.float32)

    @staticmethod
    def _z_to_xyxy(state: np.ndarray) -> Tuple[float, float, float, float]:
        """Преобразует [xc, yc, a, h] в [x1, y1, x2, y2]."""
        xc = float(state[0, 0])
        yc = float(state[1, 0])
        a = max(1e-4, float(state[2, 0]))
        h = max(1e-4, float(state[3, 0]))
        w = a * h

        return (
            xc - w / 2.0,
            yc - h / 2.0,
            xc + w / 2.0,
            yc + h / 2.0,
        )

    def predict(self) -> Tuple[float, float, float, float]:
        """Экстраполяция состояния на следующий шаг по модели движения."""
        if self.state[3, 0] + self.state[7, 0] <= 0:
            self.state[7, 0] = 0.0

        # x = F * x
        self.state = np.dot(self.F, self.state)
        # P = F * P * F^T + Q
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q

        return self._z_to_xyxy(self.state)

    def update(self, bbox_xyxy: Tuple[float, float, float, float]) -> None:
        """Коррекция состояния на основе нового измерения детектора."""
        z = self._xyxy_to_z(bbox_xyxy)

        # Невязка измерения: y = z - H * x
        y = z - np.dot(self.H, self.state)

        # S = H * P * H^T + R
        S = np.dot(np.dot(self.H, self.P), self.H.T) + self.R

        # Коэффициент Калмана: K = P * H^T * S^-1
        K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S))

        # x = x + K * y
        self.state = self.state + np.dot(K, y)

        # P = (I - K * H) * P
        I = np.eye(8, dtype=np.float32)
        self.P = np.dot(I - np.dot(K, self.H), self.P)

    def get_state(self) -> Tuple[float, float, float, float]:
        """Возвращает текущую оценку рамки [x1, y1, x2, y2]."""
        return self._z_to_xyxy(self.state)

    def get_velocity(self) -> Tuple[float, float]:
        """Возвращает текущий вектор скорости (vx, vy) в пикселях/кадр."""
        return (float(self.state[4, 0]), float(self.state[5, 0]))
