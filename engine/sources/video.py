"""
Источники видеопотоков: видеофайл, RTSP-поток, директория с изображениями, веб-камера.
"""

from __future__ import annotations

import glob
import math
import os
import time
from typing import Generator, List, Optional, Tuple
import cv2
import numpy as np

from engine.sources.base import BaseVideoSource


class VideoFileSource(BaseVideoSource):
    """Источник видео из локального файла (MP4/AVI/MKV) с возможностью зацикливания."""

    def __init__(
        self,
        filepath: str,
        loop: bool = True,
        realtime: bool = True,
    ) -> None:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"[VideoFileSource] Файл не найден: {filepath}")

        cap = cv2.VideoCapture(filepath)
        try:
            if not cap.isOpened():
                raise RuntimeError(f"[VideoFileSource] Cannot open video: {filepath}")
            fps = cap.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(fps) or fps <= 0:
                fps = 25.0
        finally:
            cap.release()

        super().__init__(fps=fps, realtime=realtime)
        self.filepath = filepath
        self.loop = loop

    def __iter__(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        cap = cv2.VideoCapture(self.filepath)
        frame_idx = 0
        t0 = time.perf_counter()
        epoch_start = time.time()

        try:
            if not cap.isOpened():
                raise RuntimeError(f"[VideoFileSource] Cannot open video: {self.filepath}")
            while not self.is_stopped():
                ret, frame = cap.read()
                if not ret or frame is None:
                    if not self.loop:
                        break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        raise RuntimeError(f"[VideoFileSource] Cannot decode video: {self.filepath}")
                    self.sequence_id += 1

                yield frame, epoch_start + frame_idx / self.fps

                frame_idx += 1
                if self.realtime:
                    target_time = t0 + frame_idx / self.fps
                    delay = target_time - time.perf_counter()
                    if delay > 0:
                        self.wait(delay)
        finally:
            cap.release()


class RtspSource(BaseVideoSource):
    """
    RTSP-источник промышленной IP-камеры.
    Поддерживает автоматическое переподключение при разрыве сетевого соединения.
    """

    def __init__(
        self,
        rtsp_url: str,
        reconnect_delay_s: float = 2.0,
        fps: float = 25.0,
    ) -> None:
        super().__init__(fps=fps, realtime=True)
        self.rtsp_url = rtsp_url
        self.reconnect_delay_s = reconnect_delay_s

    def __iter__(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        connected_once = False
        while not self.is_stopped():
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])
            try:
                if cap.isOpened():
                    if connected_once:
                        self.sequence_id += 1
                    connected_once = True
                    stream_fps = cap.get(cv2.CAP_PROP_FPS)
                    if math.isfinite(stream_fps) and stream_fps > 0:
                        self.fps = stream_fps

                    while not self.is_stopped():
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            break
                        yield frame, time.time()
            finally:
                cap.release()
            if not self.is_stopped():
                self.wait(self.reconnect_delay_s)


class ImageDirectorySource(BaseVideoSource):
    """Источник последовательности статичных изображений из папки."""

    def __init__(
        self,
        directory: str,
        fps: float = 5.0,
        loop: bool = True,
        realtime: bool = True,
    ) -> None:
        super().__init__(fps=fps, realtime=realtime)
        self.directory = directory
        self.loop = loop

        exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
        self.files: List[str] = sorted(
            f for ext in exts for f in glob.glob(os.path.join(directory, ext))
        )
        if not self.files:
            raise FileNotFoundError(f"[ImageDirectorySource] В папке {directory} нет подходящих изображений")

    def __iter__(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        i = 0
        t0 = time.perf_counter()
        epoch_start = time.time()
        while not self.is_stopped():
            if i and i % len(self.files) == 0:
                self.sequence_id += 1
            filepath = self.files[i % len(self.files)]
            frame = None
            try:
                with open(filepath, "rb") as f:
                    file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
                    frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            except Exception:
                frame = None

            if frame is not None:
                yield frame, epoch_start + i / self.fps

            i += 1
            if not self.loop and i >= len(self.files):
                break

            if self.realtime:
                target_time = t0 + i / self.fps
                delay = target_time - time.perf_counter()
                if delay > 0:
                    self.wait(delay)
