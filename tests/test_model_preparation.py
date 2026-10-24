import cv2
import numpy as np
import pytest
from engine.inference.yolo import letterbox
from linq_tools.compile_model import calibration_batch


def test_calibration_uses_exact_inference_preprocessing(tmp_path):
    frame = np.zeros((15, 23, 3), np.uint8)
    frame[:, :, 2] = 255
    ok, png = cv2.imencode('.png', frame)
    assert ok
    path = tmp_path / 'sample.png'
    path.write_bytes(png.tobytes())
    tensors, selected = calibration_batch(tmp_path, 2, lambda image: letterbox(image, (32, 32)))
    assert selected == [str(path)]
    assert tensors.shape == (1, 3, 32, 32)
    assert tensors.dtype == np.float32
    np.testing.assert_array_equal(tensors, letterbox(frame, (32, 32))[0])


def test_empty_calibration_is_an_error(tmp_path):
    with pytest.raises(ValueError, match='no images'):
        calibration_batch(tmp_path, 1, lambda image: letterbox(image, (32, 32)))
