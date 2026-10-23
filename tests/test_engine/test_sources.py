"""
Тесты видеоисточников (Video Sources) по стандарту test-master.
Покрытие: BaseVideoSource, SyntheticSource, VideoFileSource, RtspSource, ImageDirectorySource, create_video_source.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pytest

from engine.sources.base import BaseVideoSource
from engine.sources.factory import create_video_source
from engine.sources.synthetic import (
    SyntheticSource,
    _interpolate,
    _scenario_actors,
    render_scene,
)
from engine.sources.video import ImageDirectorySource, RtspSource, VideoFileSource


# ==============================================================================
# 1. SyntheticSource & Helper Functions
# ==============================================================================

def test_interpolate_boundaries_and_steps():
    """Проверка краевых условий интерполяции (до первой точки, после последней, промежуточные)."""
    pts = [(0.0, 10.0), (10.0, 20.0), (20.0, 40.0)]
    assert _interpolate(-5.0, pts) == 10.0
    assert _interpolate(0.0, pts) == 10.0
    assert _interpolate(5.0, pts) == 15.0
    assert _interpolate(15.0, pts) == 30.0
    assert _interpolate(25.0, pts) == 40.0


def test_scenario_actors_coverage():
    """Проверка всех временных отрезков сценария симуляции нарушений."""
    # t=5.0: только фоновый рабочий
    actors_5 = _scenario_actors(5.0)
    assert len(actors_5) == 1

    # t=10.0: опасная зона
    actors_10 = _scenario_actors(10.0)
    assert len(actors_10) == 2

    # t=28.0: рабочий без каски (helmet=False)
    actors_28 = _scenario_actors(28.0)
    assert any(actor[3] is False for actor in actors_28)

    # t=40.0: рабочий с телефоном (phone=True)
    actors_40 = _scenario_actors(40.0)
    assert any(actor[5] is True for actor in actors_40)

    # t=50.0: лежащий человек (lying_ratio >= 1.0)
    actors_50 = _scenario_actors(50.0)
    assert any(actor[2] >= 1.0 for actor in actors_50)


def test_synthetic_source_render_and_iteration():
    """Отрисовка кадра сцены цеха и генерация кадров через SyntheticSource."""
    frame = render_scene(15.0, width=320, height=180)
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (180, 320, 3)

    source = SyntheticSource(fps=20.0, realtime=False, max_frames=4, width=320, height=180)
    frames = list(source)
    assert len(frames) == 4
    assert frames[0][0].shape == (180, 320, 3)

    # Остановка источника
    stopped_source = SyntheticSource(fps=10.0, realtime=False)
    stopped_source.stop()
    assert len(list(stopped_source)) == 0


# ==============================================================================
# 2. VideoFileSource
# ==============================================================================

def test_video_file_source_lifecycle(tmp_path: Path):
    """Проверка работы VideoFileSource с реальным тестовым видео и обработка отсутствия файла."""
    # 1. Несуществующий файл
    with pytest.raises(FileNotFoundError):
        VideoFileSource(str(tmp_path / "non_existing.mp4"))

    # 2. Создаем тестовое видео (3 кадра)
    video_path = tmp_path / "sample.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (64, 64))
    for _ in range(3):
        out.write(np.zeros((64, 64, 3), dtype=np.uint8))
    out.release()

    # Итерация без зацикливания
    source = VideoFileSource(str(video_path), loop=False, realtime=False)
    frames = list(source)
    assert len(frames) == 3

    # Итерация с зацикливанием и принудительной остановкой
    looping_source = VideoFileSource(str(video_path), loop=True, realtime=False)
    count = 0
    for _ in looping_source:
        count += 1
        if count >= 5:
            looping_source.stop()
    assert count == 5


# ==============================================================================
# 3. ImageDirectorySource
# ==============================================================================

def test_image_directory_source(tmp_path: Path):
    """Чтение последовательности кадров из директории с изображениями."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    # 1. Пустая папка
    with pytest.raises(FileNotFoundError):
        ImageDirectorySource(str(empty_dir))

    # 2. Создаем 2 изображения
    img_dir = tmp_path / "frames"
    img_dir.mkdir()
    for idx in (1, 2):
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", img)
        with open(img_dir / f"frame_{idx}.jpg", "wb") as f:
            f.write(buf.tobytes())

    source = ImageDirectorySource(str(img_dir), fps=10.0, loop=False, realtime=False)
    frames = list(source)
    assert len(frames) == 2

    # Зацикливание
    loop_source = ImageDirectorySource(str(img_dir), fps=10.0, loop=True, realtime=False)
    count = 0
    for _ in loop_source:
        count += 1
        if count >= 4:
            loop_source.stop()
    assert count == 4


# ==============================================================================
# 4. RtspSource
# ==============================================================================

def test_rtsp_source_reconnect_and_stop():
    """Тестирование переподключения и прерывания RTSP-потока с моком VideoCapture."""
    source = RtspSource(rtsp_url="rtsp://127.0.0.1:8554/live", reconnect_delay_s=0.01, fps=25.0)

    mock_cap = MagicMock()
    # Первый вызов read: кадр есть, второй вызов read: конец потока (ret=False)
    mock_cap.isOpened.return_value = True
    mock_cap.get.return_value = 25.0
    mock_cap.read.side_effect = [
        (True, np.zeros((100, 100, 3), dtype=np.uint8)),
        (False, None),
    ]

    with patch("cv2.VideoCapture", return_value=mock_cap), patch("time.sleep") as mock_sleep:
        # Останавливаем источник после первого переподключения
        def on_sleep(_):
            source.stop()

        mock_sleep.side_effect = on_sleep

        frames = list(source)
        assert len(frames) == 1
        assert mock_cap.release.called


# ==============================================================================
# 5. create_video_source Factory
# ==============================================================================

def test_create_video_source_all_branches(tmp_path: Path):
    """Проверка всех веток фабрики видеоисточников."""
    # 1. Синтетика по умолчанию и со смещением фазы
    s1 = create_video_source("synthetic", fps=15.0, realtime=False)
    assert isinstance(s1, SyntheticSource)
    assert s1.phase == 0.0
    assert s1.fps == 15.0

    s2 = create_video_source("synthetic:12.5", realtime=False)
    assert isinstance(s2, SyntheticSource)
    assert s2.phase == 12.5

    s3 = create_video_source("synthetic:bad_val", realtime=False)
    assert isinstance(s3, SyntheticSource)
    assert s3.phase == 0.0

    # 2. RTSP и HTTP
    rtsp = create_video_source("rtsp://admin:pass@192.168.1.10:554/h264")
    assert isinstance(rtsp, RtspSource)

    http = create_video_source("http://192.168.1.10/stream")
    assert isinstance(http, RtspSource)

    # 3. Директория с изображениями
    img_dir = tmp_path / "factory_imgs"
    img_dir.mkdir()
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    with open(img_dir / "0.png", "wb") as f:
        f.write(buf.tobytes())

    dir_src = create_video_source(str(img_dir), realtime=False)
    assert isinstance(dir_src, ImageDirectorySource)

    # 4. Видеофайл
    v_file = tmp_path / "factory_vid.mp4"
    out = cv2.VideoWriter(str(v_file), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 32))
    out.write(img)
    out.release()

    vid_src = create_video_source(str(v_file), realtime=False)
    assert isinstance(vid_src, VideoFileSource)

    # 5. Неизвестная строка -> фоллбэк на синтетику
    fb_src = create_video_source("unknown_nonexistent_stream", realtime=False)
    assert isinstance(fb_src, SyntheticSource)
