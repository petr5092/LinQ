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
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.db.models.camera import Camera
    from app.schemas.incident import IncidentCreate
    from app.services.camera_hub import camera_hub
    from app.services.incident_service import create_or_merge_incident
    from app.services.notifications import notification_manager
    from app.services.notifier import notifier
    from app.storage.factory import get_storage_provider
    from engine.inference.factory import create_inference_engine
    from engine.pipeline import CVPipeline
    from engine.rules.registry import get_incident_presentation
    from engine.sources.factory import create_video_source

    logger.info(f"[{camera_id}] Запуск видеопотока из источника '{source_spec}' (бэкенд: {backend})...")
    try:
        source = create_video_source(source_spec, realtime=True, loop=True)
    except Exception as e:
        logger.warning(f"[{camera_id}] Не удалось открыть видеоисточник '{source_spec}': {e}")
        return

    def on_incident(incident, frame_bgr):
        try:
            # Сохраняем стоп-кадр последнего нарушения в CameraHub
            camera_hub.set_violation_frame(camera_id, frame_bgr)

            with SessionLocal() as db:
                camera = db.scalar(select(Camera).where(Camera.id == camera_id))
                site_id = camera.site_id if camera else "north"
                zone_name = incident.zone_id or (camera.zone if camera else "Цех № 1")

                raw_sev = getattr(incident.severity, "value", str(incident.severity)).upper()
                norm_severity = {"CRITICAL": "critical", "HIGH": "warning", "MEDIUM": "warning", "LOW": "info"}.get(
                    raw_sev, "warning"
                )

                ppe = incident.metadata.get("ppe_type")
                event_type = f"no_{ppe}" if ppe else incident.rule_name

                h, w = frame_bgr.shape[:2]
                bbox_box = None
                if incident.bbox:
                    cb = incident.bbox.clip(w, h)
                    bbox_box = [cb.x1 / w * 100, cb.y1 / h * 100, cb.width / w * 100, cb.height / h * 100]

                # Название и рекомендуемое действие для оперативного реагирования (канонический заголовок без динамического трека)
                presentation = get_incident_presentation(incident.rule_name, incident.metadata)
                title = presentation.title or "Сотрудник без каски"
                action = presentation.action or (
                    "Свяжитесь с мастером смены. Остановите работы до устранения нарушения."
                    if norm_severity == "critical"
                    else "Оповестите мастера участка для проведения целевого инструктажа."
                )

                incident_in = IncidentCreate(
                    id=incident.incident_id,
                    site_id=site_id,
                    camera_id=camera_id,
                    zone=zone_name,
                    title=title,
                    time=time.strftime("%H:%M:%S"),
                    severity=norm_severity,
                    type="person",
                    description=incident.description or "",
                    action=action,
                    image_key=incident.snapshot_path or "",
                    status="new",
                    box=bbox_box,
                    track_id=incident.track_id,
                    employee_name=f"Сотрудник #{incident.track_id}" if incident.track_id else "Иван Петров",
                    employee_role=f"Оператор станка · {zone_name}",
                    employee_number=f"00{incident.track_id:03d}" if incident.track_id else "00482",
                    employee_access="Доступ разрешён · СКУД",
                    contact_name="Иван Смирнов",
                    contact_role="Мастер смены · Корпус А",
                    contact_radio="Канал 4 · Мастер",
                    contact_phone="+7 (495) 123-45-67",
                )
                storage = get_storage_provider()
                inc_read, created = create_or_merge_incident(db, incident_in, storage)
                inc_data = inc_read.model_dump(mode="json")

                # Мгновенная рассылка в WebSocket для живого обновления видеомониторинга и журнала
                notifier.broadcast_sync({
                    "event": "INCIDENT_CREATED" if created else "INCIDENT_UPDATED",
                    "data": inc_data,
                })

                # Отправка оповещения дежурным сменам
                if created:
                    notification_manager.dispatch_incident(inc_data, incident.snapshot_path)
                    logger.info(f"[{camera_id}] Зафиксировано новое нарушение '{title}', оповещение отправлено.")
                else:
                    notification_manager.refresh_incident(inc_data)
        except Exception as err:
            logger.warning(f"[{camera_id}] Ошибка записи инцидента: {err}")

    try:
        conf_thresh = float(os.getenv("CONFIDENCE_THRESHOLD", "0.20"))
        try:
            engine = create_inference_engine(backend=backend, model_path=model_path, conf_threshold=conf_thresh)
        except Exception as err:
            logger.warning(
                f"[{camera_id}] Не удалось инициализировать бэкенд '{backend}' ({err}). "
                "Выполняется автоматическое переключение на ONNX_CPU..."
            )
            fallback_onnx = "models/onnx/safety_yolov8n.onnx"
            engine = create_inference_engine(backend="ONNX_CPU", model_path=fallback_onnx, conf_threshold=conf_thresh)

        from engine.deduplication.anti_spam import AntiSpamEngine
        cooldown = float(os.getenv("COOLDOWN_SECONDS", "20"))
        debounce = int(os.getenv("DEBOUNCE_FRAMES", "10"))
        anti_spam = AntiSpamEngine(debounce_frames=debounce, cooldown_seconds=cooldown)
        pipeline = CVPipeline(
            inference_engine=engine,
            anti_spam_engine=anti_spam,
            camera_id=camera_id,
            incident_callback=on_incident,
        )
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

            # Если на кадре зафиксировано нарушение — сохраняем стоп-кадр последнего нарушения
            if res.raw_violations or res.active_incidents or res.new_incidents:
                camera_hub.set_violation_frame(camera_id, res.annotated_frame)
            else:
                # Нарушение прекратилось — сбрасываем признак активного алерта для этой камеры,
                # чтобы при новом инциденте снова ушёл ровно один алерт
                notification_manager.resolve_camera_alert(camera_id)

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
