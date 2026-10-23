"""
Фабрика видеоисточников.
"""

from __future__ import annotations

import os
from typing import Optional
from engine.sources.base import BaseVideoSource
from engine.sources.synthetic import SyntheticSource
from engine.sources.video import ImageDirectorySource, RtspSource, VideoFileSource


def create_video_source(
    spec: str,
    fps: Optional[float] = None,
    realtime: bool = True,
    loop: bool = True,
) -> BaseVideoSource:
    """
    Создание видеоисточника по строковой спецификации:
    - 'synthetic' или 'synthetic:30' (сдвиг фазы в сек)
    - 'rtsp://user:pass@host:port/stream'
    - путь к видеофайлу ('storage/demo_videos/gate.mp4')
    - путь к папке с изображениями ('data/frames')
    """
    spec_clean = spec.strip()

    if spec_clean.startswith("synthetic"):
        phase = 0.0
        if ":" in spec_clean:
            try:
                phase = float(spec_clean.split(":", 1)[1])
            except ValueError:
                phase = 0.0
        return SyntheticSource(fps=fps or 10.0, phase=phase, realtime=realtime)

    if spec_clean.startswith("rtsp://") or spec_clean.startswith("rtsps://") or spec_clean.startswith("http://") or spec_clean.startswith("https://"):
        return RtspSource(rtsp_url=spec_clean, fps=fps or 25.0)

    if os.path.isdir(spec_clean):
        return ImageDirectorySource(directory=spec_clean, fps=fps or 5.0, loop=loop, realtime=realtime)

    if os.path.isfile(spec_clean):
        return VideoFileSource(filepath=spec_clean, loop=loop, realtime=realtime)

    # По умолчанию для синтетики, если путь не найден
    return SyntheticSource(fps=fps or 10.0, realtime=realtime)
