"""
Автономный запуск CV Worker (обработка видеопотоков на LinQ TPU / ONNX):
    python run_worker.py --backend mock --source synthetic
    python run_worker.py --backend onnx_cpu --model models/onnx/yolov8n.onnx --source rtsp://camera_ip/h264
    python run_worker.py --backend linq_tpu --model models/tpu/safety.tpu --source storage/demo_videos/gate.mp4
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import os
import signal
import sys
import threading
import time
from typing import List, Optional
import cv2
from sqlalchemy import select

from app.config import settings, BASE_DIR
from app.db.session import SessionLocal
from app.db.models.camera import Camera
from app.db.models.incident import Incident
from app.services.camera_hub import camera_hub
from app.services.notifications import notification_manager
from app.services.notifier import notifier as ws_notifier
from app.storage.factory import get_storage_provider
from engine.deduplication.anti_spam import AntiSpamEngine
from engine.inference.factory import create_inference_engine
from engine.pipeline import CVPipeline
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.engine import RulesEngine
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.phone_usage import PhoneUsageRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.proximity import ProximityRule
from engine.sources.factory import create_video_source
from engine.tracking.tracker import ByteTracker


def build_default_rules_engine() -> RulesEngine:
    """Сборка движка правил со всеми сценариями контроля ТБ."""
    rules_engine = RulesEngine()

    # 1. Опасная зона погрузчика
    zone = ZoneDefinition(
        zone_id="dz_forklift",
        name="Зона работы погрузчика",
        polygon=[(396.0, 198.0), (608.0, 198.0), (608.0, 342.0), (396.0, 342.0)],
        forbidden_classes=["person"],
    )
    rules_engine.add_rule(DangerZoneRule(zones=[zone]))

    # 2. Контроль СИЗ (каска и сигнальный жилет)
    rules_engine.add_rule(PPEComplianceRule(require_helmet=True, require_vest=True))

    # 3. Контроль падения и неподвижности
    rules_engine.add_rule(FallDetectionRule())

    # 4. Контроль использования смартфона в цеху
    rules_engine.add_rule(PhoneUsageRule())

    # 5. Опасное сближение рабочего с техникой (< 2.5 м)
    rules_engine.add_rule(ProximityRule())

    return rules_engine


def run_camera_worker(
    camera_id: str,
    source_spec: str,
    backend: str,
    model_path: Optional[str],
    stop_event: threading.Event,
) -> None:
    """Воркер обработки видеопотока конкретной камеры."""
    print(f"[{camera_id}] Запуск источника '{source_spec}' с бэкендом '{backend}'...")
    source = create_video_source(source_spec, realtime=True)
    inference_engine = create_inference_engine(backend=backend, model_path=model_path)
    tracker = ByteTracker(min_hits_to_confirm=1, high_thresh=0.35, low_thresh=0.15)
    rules_engine = build_default_rules_engine()
    anti_spam = AntiSpamEngine(
        debounce_frames=min(settings.DEBOUNCE_FRAMES, 5),
        cooldown_seconds=settings.COOLDOWN_SECONDS,
    )
    storage_provider = get_storage_provider()

    def on_incident(incident, frame_bgr):
        print(f"[{camera_id}] 🚨 ОБНАРУЖЕН ИНЦИДЕНТ: {incident.rule_name} (трек #{incident.track_id})")

        # Человекочитаемый заголовок
        title = "Нарушение требований ТБ"
        inc_type = "person"
        action = "Свяжитесь с мастером смены."
        desc = incident.description or ""

        if "helmet" in incident.rule_id.lower() or "каск" in desc.lower() or incident.metadata.get("ppe_type") == "helmet":
            title = "Сотрудник без каски"
            action = "Остановите работы, потребуйте надеть защитную каску."
            inc_type = "person"
        elif "vest" in incident.rule_id.lower() or "жилет" in desc.lower() or incident.metadata.get("ppe_type") == "vest":
            title = "Сотрудник без жилета"
            action = "Потребуйте надеть сигнальный жилет."
            inc_type = "person"
        elif "danger_zone" in incident.rule_name:
            title = "Нахождение в опасной зоне"
            action = "Подайте звуковой сигнал, покиньте опасную зону."
            inc_type = "access"
        elif "fall" in incident.rule_name:
            title = "Падение человека"
            action = "Срочно вызовите дежурного медика и остановите технику."
            inc_type = "person"
        elif "phone" in incident.rule_name:
            title = "Использование телефона"
            action = "Прекратите использование мобильного устройства в рабочей зоне."
            inc_type = "person"
        elif "proximity" in incident.rule_name:
            title = "Опасное сближение с техникой"
            action = "Остановите технику, отойдите на безопасную дистанцию."
            inc_type = "person"

        # Нормализация severity для БД (critical, warning, info)
        raw_sev = (incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity)).lower()
        if raw_sev in ("critical", "high"):
            db_sev = "critical"
        elif raw_sev in ("warning", "medium"):
            db_sev = "warning"
        else:
            db_sev = "info"

        # Короткий красивый идентификатор вида TK-XXXX
        inc_id = incident.incident_id
        if not inc_id.startswith("TK-"):
            short_id = str(abs(hash(inc_id)) % 9000 + 1000)
            inc_id = f"TK-{short_id}"

        # Координаты рамки
        box_data = None
        if incident.bbox:
            box_data = [
                round(incident.bbox.x1, 1),
                round(incident.bbox.y1, 1),
                round(incident.bbox.width, 1),
                round(incident.bbox.height, 1),
            ]

        time_str = datetime.now().strftime("%H:%M:%S")
        site_id = "north"
        zone_name = "Цех № 1"
        camera_name = camera_id

        # Сохранение в PostgreSQL
        try:
            with SessionLocal() as db:
                cam_rec = db.get(Camera, camera_id)
                if cam_rec:
                    site_id = cam_rec.site_id
                    zone_name = cam_rec.zone
                    camera_name = cam_rec.name

                existing = db.scalar(select(Incident).where(Incident.id == inc_id))
                if not existing:
                    db_inc = Incident(
                        id=inc_id,
                        site_id=site_id,
                        camera_id=camera_id,
                        zone=zone_name,
                        title=title,
                        time=time_str,
                        severity=db_sev,
                        type=inc_type,
                        description=desc or title,
                        action=action,
                        image_key=incident.snapshot_path or "",
                        status="new",
                        box=box_data,
                        track_id=incident.track_id,
                        confidence=0.92,
                        is_verified=False,
                    )
                    db.add(db_inc)
                    db.commit()
        except Exception as e:
            print(f"[{camera_id}] Предупреждение записи инцидента в БД: {e}")

        # Поиск абсолютного пути к снапшоту для передачи в Telegram
        abs_snap = None
        if incident.snapshot_path:
            rel = incident.snapshot_path.replace("/static/snapshots/", "").lstrip("/\\")
            for base in (str(settings.LOCAL_SNAPSHOTS_DIR), os.path.join(str(BASE_DIR), "storage", "snapshots")):
                cand = os.path.join(base, rel)
                if os.path.isfile(cand):
                    abs_snap = cand
                    break

        inc_data = {
            "id": inc_id,
            "site_id": site_id,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "zone": zone_name,
            "zone_name": zone_name,
            "title": title,
            "rule_name": title,
            "rule_label": title,
            "time": time_str,
            "timestamp_str": f"{time_str} {datetime.now().strftime('%d.%m.%Y')}",
            "severity": db_sev,
            "type": inc_type,
            "description": desc or title,
            "action": action,
            "image_key": incident.snapshot_path or "",
            "snapshot_url": incident.snapshot_path or "",
            "status": "new",
            "box": box_data,
            "track_id": incident.track_id,
            "is_verified": False,
        }

        # Оповещение веб-дашборда через WebSocket
        ws_notifier.broadcast_sync({
            "event": "INCIDENT_NEW",
            "data": inc_data,
        })
        ws_notifier.broadcast_sync({
            "event": "INCIDENT_CREATED",
            "data": inc_data,
        })

        # Мгновенная отправка фото-оповещения в Telegram
        notification_manager.dispatch_incident(inc_data, abs_snap)

    pipeline = CVPipeline(
        inference_engine=inference_engine,
        tracker=tracker,
        rules_engine=rules_engine,
        anti_spam_engine=anti_spam,
        storage_provider=storage_provider,
        incident_callback=on_incident,
        camera_id=camera_id,
    )

    camera_hub.set_camera_state(camera_id, "online")

    # Асинхронный воркер инференса для обеспечения гладких 25-30 FPS видеопотока без слоу-мо
    latest_frame_for_inf = None
    latest_detections = []
    latest_inf_time_ms = 18.4
    inf_lock = threading.Lock()
    inf_stop_event = threading.Event()

    def async_inference_worker():
        nonlocal latest_detections, latest_inf_time_ms
        while not inf_stop_event.is_set() and not stop_event.is_set():
            cur_frame = None
            with inf_lock:
                if latest_frame_for_inf is not None:
                    cur_frame = latest_frame_for_inf.copy()
            if cur_frame is not None:
                try:
                    t_inf0 = time.perf_counter()
                    inf_res = inference_engine.infer(cur_frame)
                    t_inf1 = time.perf_counter()
                    latest_detections = inf_res.detections
                    latest_inf_time_ms = round((t_inf1 - t_inf0) * 1000.0, 2)
                except Exception as e:
                    pass
            time.sleep(0.005)

    inf_thread = threading.Thread(target=async_inference_worker, daemon=True, name=f"inf_{camera_id}")
    inf_thread.start()

    frame_count = 0
    t_start = time.perf_counter()

    for frame_bgr, ts in source:
        if stop_event.is_set():
            break

        # Автоматическое приведение к веб-разрешению (720p) для мгновенного рендеринга
        h, w = frame_bgr.shape[:2]
        if w > 1280:
            scale = 1280.0 / w
            frame_bgr = cv2.resize(frame_bgr, (1280, int(h * scale)), interpolation=cv2.INTER_AREA)

        with inf_lock:
            latest_frame_for_inf = frame_bgr

        res = pipeline.process_frame(
            frame_bgr,
            timestamp=ts,
            detections=latest_detections,
            inference_time_ms=latest_inf_time_ms,
        )
        camera_hub.set_frame(camera_id, res.annotated_frame)

        frame_count += 1
        if frame_count % 10 == 0:
            elapsed = time.perf_counter() - t_start
            cur_fps = 10.0 / elapsed if elapsed > 0 else 0.0
            t_start = time.perf_counter()
            camera_hub.update_metrics(
                camera_id=camera_id,
                fps=cur_fps,
                detect_time_ms=latest_inf_time_ms,
                latency_ms=res.metrics.total_time_ms,
            )

    inf_stop_event.set()
    camera_hub.set_camera_state(camera_id, "stopped")
    print(f"[{camera_id}] Поток завершен.")


def main():
    parser = argparse.ArgumentParser(description="Запуск CV Worker аналитики ТБ LinQ Safety Guard")
    parser.add_argument("--source", action="append", help="Источник видео (synthetic, synthetic:30, rtsp://..., файл.mp4)")
    parser.add_argument("--backend", default=None, choices=["linq_tpu", "linq_remote", "onnx_cpu", "mock"],
                        help="Вычислительный бэкенд инференса (по умолчанию из .env)")
    parser.add_argument("--model", default=None, help="Путь к файлу нейросети (.tpu или .onnx)")
    parser.add_argument("--endpoint", default=None, help="URL удаленного сервиса LinQ TPU (например http://10.0.114.5:8080)")
    parser.add_argument("--demo-video", action="store_true", help="использовать видео из storage/demo_videos/construction_safety.mp4")
    parser.add_argument("--web", action="store_true", help="Запустить веб-сервер FastAPI параллельно с воркером")
    parser.add_argument("--port", type=int, default=8000, help="Порт веб-сервера")
    args = parser.parse_args()

    if args.endpoint:
        os.environ["LINQ_TPU_URL"] = args.endpoint
    backend = args.backend or settings.INFERENCE_BACKEND.lower()
    model = args.model or (settings.TPU_MODEL_PATH if "tpu" in backend else settings.ONNX_MODEL_PATH)
    if args.demo_video:
        sources = ["storage/demo_videos/construction_safety.mp4"]
    else:
        sources = args.source or ["synthetic", "synthetic:30"]

    stop_event = threading.Event()
    threads = []

    notification_manager.start()

    for idx, src_spec in enumerate(sources, 1):
        cam_id = f"CAM-{idx:02d}"
        t = threading.Thread(
            target=run_camera_worker,
            args=(cam_id, src_spec, backend, model, stop_event),
            daemon=True,
            name=f"worker_{cam_id}",
        )
        t.start()
        threads.append(t)

    print(f"\n[LinQ Worker] Запущен мониторинг {len(sources)} камер на бэкенде '{backend}'")

    if args.web:
        import uvicorn
        from app.main import app
        print(f"[Web API] Доступно на http://127.0.0.1:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nОстановка воркеров...")
            stop_event.set()
            for t in threads:
                t.join(timeout=2.0)
            notification_manager.stop()


if __name__ == "__main__":
    main()
