"""Детекторы. Все возвращают list[Detection] из кадра.

Структура повторяет маршрут LinQ: препроцессинг -> инференс -> постпроцессинг.
Препроцессинг и постпроцессинг общие, меняется только infer():
  OnnxDetector  — onnxruntime на CPU (эталон и запасной вариант);
  LinQDetector  — TPU через ваш адаптер linq_adapter.py;
  MockDetector  — отдаёт разметку синтетической сцены (демо и тесты).
"""
import importlib
import threading
import time

import numpy as np
from PIL import Image

from . import config
from .models import Detection


def letterbox(img, size):
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = round(h * r), round(w * r)
    im = np.asarray(Image.fromarray(img).resize((nw, nh), Image.BILINEAR))
    canvas = np.full((size, size, 3), 114, np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = im
    return canvas, r, left, top


def to_tensor(canvas):
    return (canvas.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]


def nms(boxes, scores, thr):
    order = scores.argsort()[::-1]
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        rest = order[1:]
        if not rest.size:
            break
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        iou = inter / (areas[i] + areas[rest] - inter + 1e-9)
        order = rest[iou < thr]
    return keep


def decode_yolo(out, names, r, left, top, shape, conf_thr, iou_thr):
    """Разбор выхода YOLOv8-стиля: (1, 4+nc, N) или (1, N, 4+nc), без objectness."""
    p = np.asarray(out, dtype=np.float32)
    p = p[0] if p.ndim == 3 else p
    if p.shape[0] < p.shape[1]:
        p = p.T
    sc = p[:, 4:4 + len(names)]
    cls_id, conf = sc.argmax(1), sc.max(1)
    m = conf >= conf_thr
    p, cls_id, conf = p[m], cls_id[m], conf[m]
    if not len(p):
        return []
    cx, cy, w, h = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 1)
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - left) / r
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - top) / r
    H, W = shape[:2]
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, W)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, H)
    keep = nms(boxes + cls_id[:, None] * 10000.0, conf, iou_thr)  # NMS по классам
    return [Detection(names[int(cls_id[i])], float(conf[i]), tuple(float(v) for v in boxes[i]))
            for i in keep]


class Detector:
    name = "base"

    def __init__(self):
        self._lock = threading.Lock()   # один ускоритель — общий для всех камер
        self.last = {"pre_ms": 0.0, "infer_ms": 0.0, "post_ms": 0.0}

    def detect(self, frame):
        with self._lock:
            return self._detect(frame)


class TensorDetector(Detector):
    def __init__(self, names=None, size=None, conf=None, iou=None):
        super().__init__()
        self.names = names or config.CLASS_NAMES
        self.size = size or config.INPUT_SIZE
        self.conf = conf or config.CONF_THR
        self.iou = iou or config.NMS_IOU

    def infer(self, tensor):
        raise NotImplementedError

    def _detect(self, frame):
        t0 = time.perf_counter()
        canvas, r, left, top = letterbox(frame.img, self.size)
        tensor = to_tensor(canvas)
        t1 = time.perf_counter()
        out = self.infer(tensor)
        t2 = time.perf_counter()
        dets = decode_yolo(out, self.names, r, left, top, frame.img.shape, self.conf, self.iou)
        t3 = time.perf_counter()
        self.last = {"pre_ms": (t1 - t0) * 1e3, "infer_ms": (t2 - t1) * 1e3, "post_ms": (t3 - t2) * 1e3}
        return dets


class OnnxDetector(TensorDetector):
    name = "onnxruntime-cpu"

    def __init__(self, model_path, **kw):
        super().__init__(**kw)
        import onnxruntime as ort
        self.sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.inp = self.sess.get_inputs()[0].name

    def infer(self, tensor):
        return self.sess.run(None, {self.inp: tensor})[0]


class LinQDetector(TensorDetector):
    """Инференс на LinQ TPU. Вся работа с API — в вашем файле linq_adapter.py
    (шаблон: linq_adapter_template.py). Адаптер должен вернуть функцию
    run(tensor: np.ndarray) -> np.ndarray, где выход — тензор модели."""
    name = "linq-tpu"

    def __init__(self, program_path, **kw):
        super().__init__(**kw)
        try:
            adapter = importlib.import_module("linq_adapter")
        except ImportError as e:
            raise SystemExit("Не найден linq_adapter.py. Скопируйте linq_adapter_template.py "
                             "в linq_adapter.py и допишите вызовы API LinQ.") from e
        self._run = adapter.load(program_path)

    def infer(self, tensor):
        return self._run(tensor)


class MockDetector(Detector):
    """Отдаёт готовую разметку синтетической сцены. Нужен, чтобы демо и тесты
    работали без модели. Честные цифры производительности он не даёт."""
    name = "mock (разметка сцены)"

    def _detect(self, frame):
        self.last = {"pre_ms": 0.0, "infer_ms": 0.0, "post_ms": 0.0}
        return list(frame.meta.get("gt", []))


def make_detector(backend, model=None, names=None):
    if backend == "mock":
        return MockDetector()
    if backend == "onnx":
        return OnnxDetector(model, names=names)
    if backend == "linq":
        return LinQDetector(model, names=names)
    raise ValueError(f"неизвестный backend: {backend}")
