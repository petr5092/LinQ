"""
Подготовка, экспорт и валидация модели детекции СИЗ (YOLOv8n) для LinQ Safety Guard.
Загружает веса легковесной модели детекции СИЗ (YOLOv8n-PPE) из открытого источника,
выполняет экспорт в строго статичный формат ONNX (1, 3, 640, 640) без динамических осей
для совместимости с LinQ TPU H1M и проверяет инференс через ONNXRuntime.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
import numpy as np

# Определение путей
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
CHECKPOINT_DIR = MODELS_DIR / "checkpoints"
ONNX_DIR = MODELS_DIR / "onnx"

CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
ONNX_DIR.mkdir(parents=True, exist_ok=True)

MODEL_URL = "https://huggingface.co/baskarmother/yolov8-ppe-construction/resolve/main/best.pt"
PT_PATH = CHECKPOINT_DIR / "yolov8n_ppe.pt"
TARGET_ONNX_PATH = ONNX_DIR / "safety_yolov8n.onnx"
CLASSES_CONFIG_PATH = ONNX_DIR / "safety_yolov8n_classes.json"

# Карта соответствия исходных классов модели классам LinQ Safety Guard
# Исходные 17 классов:
# 0: barricade, 1: dumpster, 2: excavators, 3: gloves, 4: hardhat, 5: mask,
# 6: no-hardhat, 7: no-mask, 8: no-safety vest, 9: person, 10: safety net,
# 11: safety shoes, 12: safety vest, 13: dump truck, 14: mini-van, 15: truck, 16: wheel loader
CANONICAL_CLASS_MAP = {
    0: "barricade",
    1: "dumpster",
    2: "excavator",
    3: "gloves",
    4: "helmet",        # hardhat -> helmet
    5: "mask",
    6: "no_helmet",     # no-hardhat -> no_helmet
    7: "no_mask",
    8: "no_vest",       # no-safety vest -> no_vest
    9: "person",        # person
    10: "safety_net",
    11: "safety_shoes",
    12: "vest",         # safety vest -> vest
    13: "dump_truck",
    14: "minivan",
    15: "truck",
    16: "wheel_loader"
}


def download_checkpoint(url: str, dest_path: Path) -> None:
    if dest_path.exists() and dest_path.stat().st_size > 1_000_000:
        print(f"[1/4] Чекпоинт уже существует: {dest_path} ({dest_path.stat().st_size / (1024*1024):.2f} MB)")
        return

    print(f"[1/4] Загрузка открытых весов YOLOv8n PPE из {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req, timeout=30) as response, open(dest_path, "wb") as out_file:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 65536
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                percent = downloaded / total_size * 100
                sys.stdout.write(f"\r  Загружено: {downloaded / (1024*1024):.2f} / {total_size / (1024*1024):.2f} MB ({percent:.1f}%)")
                sys.stdout.flush()
    print("\n  Загрузка успешно завершена.")


def export_to_onnx(pt_path: Path, onnx_dest: Path) -> None:
    print(f"[2/4] Экспорт модели в статичный ONNX (640x640)...")
    from ultralytics import YOLO

    model = YOLO(str(pt_path))
    print(f"  Исходные классы модели ({len(model.names)}): {model.names}")

    # Экспорт с жесткими статическими размерностями [1, 3, 640, 640] без динамических батчей
    exported_path = model.export(
        format="onnx",
        imgsz=640,
        dynamic=False,
        opset=12,
        simplify=True,
    )
    exported_path = Path(exported_path)

    if exported_path.resolve() != onnx_dest.resolve():
        if onnx_dest.exists():
            onnx_dest.unlink()
        exported_path.rename(onnx_dest)

    print(f"  Экспорт завершен: {onnx_dest} ({onnx_dest.stat().st_size / (1024*1024):.2f} MB)")

    # Сохраняем маппинг классов
    with open(CLASSES_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(CANONICAL_CLASS_MAP, f, indent=2, ensure_ascii=False)
    print(f"  Маппинг классов сохранен в: {CLASSES_CONFIG_PATH}")


def validate_onnx_model(onnx_path: Path) -> None:
    print(f"[3/4] Валидация структуры графа ONNX и верификация через ONNXRuntime...")
    import onnx
    import onnxruntime as ort

    onnx_model = onnx.load(str(onnx_path))
    onnx.checker.check_model(onnx_model)
    print("  ONNX топология корректна (проверка onnx.checker пройдена).")

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inputs = session.get_inputs()
    outputs = session.get_outputs()

    print(f"  Входные узлы: {[(i.name, i.shape, i.type) for i in inputs]}")
    print(f"  Выходные узлы: {[(o.name, o.shape, o.type) for o in outputs]}")

    # Проверка статичности размерностей
    input_shape = inputs[0].shape
    assert input_shape == [1, 3, 640, 640], f"Ошибка: ожидался статичный размер [1, 3, 640, 640], получен {input_shape}"

    # Тестовый прогон на синтетическом тензоре
    dummy_input = np.random.randn(1, 3, 640, 640).astype(np.float32)
    start_time = time.perf_counter()
    raw_output = session.run([outputs[0].name], {inputs[0].name: dummy_input})[0]
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    print(f"  Выходной тензор: shape={raw_output.shape}, dtype={raw_output.dtype}")
    print(f"  Задержка одиночного инференса на CPU: {latency_ms:.2f} мс (~{1000.0 / latency_ms:.1f} FPS)")

    assert not np.isnan(raw_output).any(), "Выходной тензор содержит NaN!"
    assert not np.isinf(raw_output).any(), "Выходной тензор содержит Inf!"
    assert raw_output.shape == (1, 4 + len(CANONICAL_CLASS_MAP), 8400), (
        f"Неожиданный формат выхода: {raw_output.shape}"
    )
    print("  Тестовый прогон инференса успешно завершен!")


def test_with_local_onnx_engine(onnx_path: Path) -> None:
    print(f"[4/4] Тестирование в связке с движком LinQ LocalONNXEngine...")
    sys.path.insert(0, str(PROJECT_ROOT))
    import cv2
    from engine.inference.local_onnx import LocalONNXEngine

    engine = LocalONNXEngine(
        model_path=str(onnx_path),
        conf_threshold=0.25,
        iou_threshold=0.45,
        class_names=CANONICAL_CLASS_MAP,
    )

    # Синтезируем тестовое изображение со светлым фоном и прямоугольниками
    test_img = np.full((720, 1280, 3), 200, dtype=np.uint8)
    cv2.putText(test_img, "LinQ Safety Test Frame", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)

    result = engine.infer(test_img)
    print(f"  Инференс через LocalONNXEngine выполнен:")
    print(f"    - Детекций: {len(result.detections)}")
    print(f"    - Препроцессинг: {result.metrics.preprocess_time_ms:.2f} мс")
    print(f"    - Инференс: {result.metrics.inference_time_ms:.2f} мс")
    print(f"    - Постпроцессинг: {result.metrics.postprocess_time_ms:.2f} мс")
    print(f"    - Общее время: {result.metrics.total_time_ms:.2f} мс ({result.metrics.fps:.1f} FPS)")


def main() -> None:
    print("=== Подготовка легковесной модели детекции СИЗ (YOLOv8n) ===")
    download_checkpoint(MODEL_URL, PT_PATH)
    export_to_onnx(PT_PATH, TARGET_ONNX_PATH)
    validate_onnx_model(TARGET_ONNX_PATH)
    test_with_local_onnx_engine(TARGET_ONNX_PATH)
    print("\n Все этапы успешно пройдены!")


if __name__ == "__main__":
    main()
