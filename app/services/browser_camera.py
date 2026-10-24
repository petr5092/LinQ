"""Inference pipelines for cameras captured by an operator's browser."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Dict

import cv2
import numpy as np

from app.config import BASE_DIR, settings
from app.db.models.camera import Camera
from engine.deduplication.anti_spam import AntiSpamEngine
from engine.incident_client import IncidentClient
from engine.inference.factory import create_inference_engine
from engine.pipeline import CVPipeline
from engine.rules.engine import RulesEngine
from engine.rules.ppe_compliance import PPEComplianceRule

log = logging.getLogger(__name__)

_lock = threading.RLock()
_pipelines: Dict[str, CVPipeline] = {}
_frame_ids: Dict[str, int] = {}
_sink: IncidentClient | None = None


class BrowserCameraConfigurationError(RuntimeError):
    """The configured inference backend cannot process browser camera frames."""


def _get_sink() -> IncidentClient:
    global _sink
    if _sink is None:
        outbox = BASE_DIR / "storage" / "browser_camera_outbox"
        api_url = f"http://127.0.0.1:{settings.PORT}{settings.API_V1_PREFIX}"
        _sink = IncidentClient(api_url, outbox)
        _sink.start()
    return _sink


def _get_pipeline(camera: Camera) -> CVPipeline:
    if settings.INFERENCE_BACKEND.upper() == "LINQ_TPU":
        raise BrowserCameraConfigurationError(
            "Захват из браузера сейчас несовместим с параллельным TPU-воркером. "
            "Для этого режима установите INFERENCE_BACKEND=ONNX_CPU."
        )
    if settings.INFERENCE_BACKEND.upper() != "ONNX_CPU":
        raise BrowserCameraConfigurationError(
            "Для реальной камеры требуется INFERENCE_BACKEND=ONNX_CPU; MOCK не выполняет детекцию."
        )

    pipeline = _pipelines.get(camera.id)
    if pipeline is not None:
        return pipeline

    model_path = Path(settings.ONNX_MODEL_PATH)
    if not model_path.is_absolute():
        model_path = BASE_DIR / model_path
    try:
        inference = create_inference_engine(
            backend="ONNX_CPU",
            model_path=str(model_path),
            conf_threshold=settings.CONFIDENCE_THRESHOLD,
            iou_threshold=settings.IOU_THRESHOLD,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise BrowserCameraConfigurationError(
            f"Не удалось загрузить ONNX-модель для камеры: {exc}"
        ) from exc
    classes = set(inference.class_names.values())
    if "person" not in classes or not classes.intersection({"helmet", "no_helmet"}):
        inference.close()
        raise BrowserCameraConfigurationError(
            "ONNX-модель должна содержать классы person и helmet либо no_helmet."
        )

    sink = _get_sink()
    camera_info = {
        "camera_id": camera.id,
        "site_id": camera.site_id,
        "zone": camera.zone,
    }
    rules = RulesEngine([PPEComplianceRule(require_helmet=True, require_vest=False)])
    pipeline = CVPipeline(
        inference_engine=inference,
        rules_engine=rules,
        anti_spam_engine=AntiSpamEngine(
            debounce_frames=settings.DEBOUNCE_FRAMES,
            cooldown_seconds=settings.COOLDOWN_SECONDS,
        ),
        incident_callback=lambda incident, frame: sink.submit(incident, frame, camera_info),
        camera_id=camera.id,
    )
    _pipelines[camera.id] = pipeline
    _frame_ids[camera.id] = 0
    log.info("Browser camera inference initialized camera=%s backend=ONNX_CPU", camera.id)
    return pipeline


def process_browser_frame(camera: Camera, jpeg: bytes) -> dict:
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Не удалось прочитать JPEG-кадр.")
    if image.shape[1] > 1920 or image.shape[0] > 1080:
        raise ValueError("Разрешение кадра не должно превышать 1920×1080.")

    with _lock:
        pipeline = _get_pipeline(camera)
        _frame_ids[camera.id] += 1
        result = pipeline.process_frame(
            image,
            frame_id=_frame_ids[camera.id],
            camera_id=camera.id,
            render_annotations=False,
        )
        detections = [
            {
                "class_name": detection.class_name,
                "confidence": round(detection.confidence, 3),
                "bbox": list(detection.bbox.as_xyxy()),
            }
            for detection in result.detections
        ]
        return {
            "camera_id": camera.id,
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
            "detections": detections,
            "violations": [
                {
                    "description": violation.description,
                    "class_name": violation.metadata.get("ppe_type", "ppe"),
                    "bbox": list(violation.bbox.as_xyxy()),
                }
                for violation in result.raw_violations
            ],
            "new_incidents": [incident.description for incident in result.new_incidents],
            "metrics": {
                "backend": result.metrics.backend_name,
                "inference_ms": result.metrics.inference_time_ms,
                "fps": result.metrics.fps,
            },
        }


def close_browser_camera_pipelines() -> None:
    global _sink
    with _lock:
        for pipeline in _pipelines.values():
            pipeline.inference_engine.close()
        _pipelines.clear()
        _frame_ids.clear()
        if _sink is not None:
            _sink.close()
            _sink = None
