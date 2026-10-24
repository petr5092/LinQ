"""
Сервис запуска фонового CV-воркера для онлайн-камер LinQ Safety Guard.
Обеспечивает детекцию СИЗ/опасных зон, рассылку алертов и живой MJPEG-видеопоток в интерфейс диспетчера.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger("linq.cv_service")


def run_cv_camera_worker(
    camera_id: str,
    source_spec: str,
    backend: str,
    model_path: Optional[str],
    stop_event: threading.Event,
) -> None:
    """Фоновый воркер нейросетевой обработки для live-стриминга камеры и фиксации нарушений."""
    from app.db.session import SessionLocal
    from app.db.models.incident import Incident
    from app.services.camera_hub import camera_hub
    from app.services.notifications import notification_manager
    from engine.inference.factory import create_inference_engine
    from engine.pipeline import CVPipeline
    from engine.sources.factory import create_video_source

    logger.info(f"[{camera_id}] Запуск видеопотока из источника '{source_spec}' (бэкенд: {backend})...")
    try:
        source = create_video_source(source_spec, realtime=True, loop=True)
    except Exception as e:
        logger.warning(f"[{camera_id}] Не удалось открыть видеоисточник '{source_spec}': {e}")
        return

    def on_incident(incident, frame_bgr):
        try:
            with SessionLocal() as db:
                db_inc = Incident(
                    id=incident.incident_id,
                    camera_id=camera_id,
                    incident_type=incident.rule_name,
                    severity=incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity),
                    status="new",
                    snapshot_url=incident.snapshot_path,
                    bounding_boxes={"bbox": incident.bbox.as_xyxy()} if incident.bbox else None,
                    rule_params={"zone_id": incident.zone_id, "track_id": incident.track_id},
                )
                db.add(db_inc)
                db.commit()
        except Exception as err:
            logger.warning(f"[{camera_id}] Ошибка записи инцидента в БД: {err}")

        inc_data = {
            "id": incident.incident_id,
            "rule_name": incident.rule_name,
            "rule_label": incident.description or incident.rule_name,
            "severity": incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity),
            "camera_id": camera_id,
            "camera_name": camera_id,
            "zone_id": incident.zone_id,
            "status": "new",
        }
        notification_manager.dispatch_incident(inc_data, incident.snapshot_path)

    try:
        try:
            engine = create_inference_engine(backend=backend, model_path=model_path)
        except Exception as err:
            logger.warning(
                f"[{camera_id}] Не удалось инициализировать бэкенд '{backend}' ({err}). "
                "Выполняется автоматическое переключение на ONNX_CPU..."
            )
            fallback_onnx = "models/onnx/safety_yolov8n.onnx"
            engine = create_inference_engine(backend="ONNX_CPU", model_path=fallback_onnx)

        pipeline = CVPipeline(inference_engine=engine, camera_id=camera_id, incident_callback=on_incident)
    except Exception as e:
        logger.warning(f"[{camera_id}] Ошибка инициализации CVPipeline: {e}")
        return

    camera_hub.set_camera_state(camera_id, "online")
    frame_count = 0
    t_start = time.perf_counter()

    try:
        for frame_bgr, ts in source:
            if stop_event.is_set():
                break

            res = pipeline.process_frame(frame_bgr, timestamp=ts)
            camera_hub.set_frame(camera_id, res.annotated_frame)

            frame_count += 1
            if frame_count % 10 == 0:
                elapsed = time.perf_counter() - t_start
                cur_fps = 10.0 / elapsed if elapsed > 0 else 0.0
                t_start = time.perf_counter()
                camera_hub.update_metrics(
                    camera_id=camera_id,
                    fps=cur_fps,
                    detect_time_ms=res.metrics.inference_time_ms,
                    latency_ms=res.metrics.total_time_ms,
                )
    except Exception as e:
        logger.warning(f"[{camera_id}] Ошибка обработки кадров: {e}")
    finally:
        source.stop()
        camera_hub.set_camera_state(camera_id, "stopped")
        logger.info(f"[{camera_id}] Поток камеры остановлен.")
