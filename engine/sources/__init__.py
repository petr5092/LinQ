"""
Пакет видеоисточников (Video Sources) для CV Engine.
"""

from engine.sources.base import BaseVideoSource
from engine.sources.factory import create_video_source
from engine.sources.synthetic import SyntheticSource, render_scene
from engine.sources.video import ImageDirectorySource, RtspSource, VideoFileSource

__all__ = [
    "BaseVideoSource",
    "create_video_source",
    "SyntheticSource",
    "render_scene",
    "VideoFileSource",
    "RtspSource",
    "ImageDirectorySource",
]
