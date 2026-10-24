"""
Сервис CameraHub — буферизация live-кадров, MJPEG-стриминг и мониторинг состояния камер.
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from typing import AsyncGenerator, Dict, List, Optional, Tuple
import cv2
import numpy as np


class CameraHub:
    """
    Централизованный диспетчер видеопотоков и телеметрии камер.
    Позволяет веб-клиентам получать живой MJPEG-поток и снапшоты,
    а также отслеживает здоровье источников (онлайн/офлайн).
    """

    STALE_TIMEOUT_SECONDS = 10.0

    def __init__(self) -> None:
        self._frames: Dict[str, Tuple[int, bytes]] = {}
        self._cond = threading.Condition()
        self._states: Dict[str, dict] = {}
        self._state_lock = threading.Lock()
        self._metrics: Dict[str, dict] = {}
        self._metrics_lock = threading.Lock()

    def set_frame(self, camera_id: str, frame_data: np.ndarray | bytes) -> None:
        """Сохранение свежего кадра камеры для раздачи (принимает BGR numpy-массив или JPEG байты)."""
        if isinstance(frame_data, np.ndarray):
            h, w = frame_data.shape[:2]
            # Масштабирование для сверхбыстрой передачи и мгновенного отображения в браузере
            if w > 1280:
                scale = 1280.0 / w
                frame_data = cv2.resize(frame_data, (1280, int(h * scale)), interpolation=cv2.INTER_AREA)
            success, enc = cv2.imencode(".jpg", frame_data, [cv2.IMWRITE_JPEG_QUALITY, 75])
            jpeg_bytes = enc.tobytes() if success else b""
        else:
            jpeg_bytes = frame_data

        now = time.time()
        with self._cond:
            seq = self._frames.get(camera_id, (0, b""))[0] + 1
            self._frames[camera_id] = (seq, jpeg_bytes)
            self._cond.notify_all()

        with self._state_lock:
            state = self._states.setdefault(camera_id, {
                "started_at": now,
                "frames_count": 0,
                "status": "online",
            })
            state["frames_count"] = state.get("frames_count", 0) + 1
            state["last_frame_at"] = now
            state["status"] = "online"

    def get_frame(self, camera_id: str) -> Optional[bytes]:
        """Мгновенное получение последнего JPEG-кадра без блокировки."""
        with self._cond:
            entry = self._frames.get(camera_id)
            return entry[1] if entry else None

    def wait_frame(self, camera_id: str, last_seq: int, timeout: float = 3.0) -> Tuple[int, Optional[bytes]]:
        """Ожидание появления нового кадра (для генерации MJPEG)."""
        with self._cond:
            self._cond.wait_for(
                lambda: self._frames.get(camera_id, (0, b""))[0] != last_seq,
                timeout=timeout,
            )
            return self._frames.get(camera_id, (0, b""))

    async def mjpeg_generator(self, camera_id: str) -> AsyncGenerator[bytes, None]:
        """Асинхронный генератор кадров в формате multipart/x-mixed-replace."""
        last_seq = 0
        while True:
            # Выполняем ожидание в пуле потоков, чтобы не блокировать event loop FastAPI
            seq, data = await asyncio.to_thread(self.wait_frame, camera_id, last_seq, 2.0)
            if data and seq != last_seq:
                last_seq = seq
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(data)).encode() + b"\r\n\r\n"
                    + data + b"\r\n"
                )
            else:
                await asyncio.sleep(0.05)

    def set_camera_state(self, camera_id: str, status: str, **kwargs) -> None:
        """Обновление статуса камеры (online, offline, error, starting)."""
        now = time.time()
        with self._state_lock:
            state = self._states.setdefault(camera_id, {"started_at": now, "frames_count": 0})
            state.update(status=status, updated_at=now, **kwargs)

    def get_camera_statuses(self) -> List[dict]:
        """Получение списка оперативных статусов всех зарегистрированных камер."""
        now = time.time()
        result = []
        with self._state_lock:
            for cam_id, state in self._states.items():
                last_ts = state.get("last_frame_at")
                age_s = round(now - last_ts, 1) if last_ts else None
                status = state.get("status", "unknown")

                # Если кадров нет дольше STALE_TIMEOUT_SECONDS, помечаем офлайн
                if status not in ("error", "stopped"):
                    if age_s is not None and age_s > self.STALE_TIMEOUT_SECONDS:
                        status = "offline"
                    elif age_s is None and (now - state.get("started_at", now)) > self.STALE_TIMEOUT_SECONDS:
                        status = "offline"

                metrics = self._metrics.get(cam_id, {})
                result.append({
                    "camera_id": cam_id,
                    "status": status,
                    "last_frame_at": last_ts,
                    "last_frame_age_seconds": age_s,
                    "frames_count": state.get("frames_count", 0),
                    "fps": metrics.get("fps", 0.0),
                    "detect_time_ms": metrics.get("detect_time_ms", 0.0),
                    "latency_ms": metrics.get("latency_ms", 0.0),
                    "error": state.get("error"),
                })
        return result

    def update_metrics(self, camera_id: str, fps: float, detect_time_ms: float, latency_ms: float) -> None:
        """Обновление показателей производительности камеры."""
        with self._metrics_lock:
            self._metrics[camera_id] = {
                "fps": round(fps, 1),
                "detect_time_ms": round(detect_time_ms, 2),
                "latency_ms": round(latency_ms, 2),
                "updated_at": time.time(),
            }

    def get_metrics(self, camera_id: str) -> dict:
        """Получение метрик конкретной камеры."""
        with self._metrics_lock:
            return dict(self._metrics.get(camera_id, {
                "fps": 0.0,
                "detect_time_ms": 0.0,
                "latency_ms": 0.0,
                "updated_at": None,
            }))


camera_hub = CameraHub()
