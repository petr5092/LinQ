"""Запуск: python run.py                      — демо на синтетических камерах без модели
          python run.py --backend onnx --model best.onnx --source cam.mp4 --source rtsp://...
          python run.py --backend linq --model program.tpu --source cam.mp4"""
import argparse
import threading

from app import config, sources
from app.detector import make_detector
from app.enterprise import EnterpriseConfig
from app.hub import Hub
from app.logging_config import configure_logging, shutdown_logging
from app.notify.core import Notifier, from_env
from app.pipeline import CameraWorker
from app.server import serve
from app.store import EventStore, ZoneStore


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", action="append", help="synthetic | synthetic:30 | файл | папка | rtsp://… (можно несколько)")
    ap.add_argument("--backend", default="mock", choices=["mock", "onnx", "linq"])
    ap.add_argument("--model", help="путь к .onnx (onnx) или Программе для TPU (linq)")
    ap.add_argument("--classes", help="имена классов через запятую, если отличаются от app/config.py")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1", help="интерфейс веб-панели (по умолчанию только этот компьютер)")
    ap.add_argument("--no-notifications", action="store_true",
                    help="не загружать токены и отключить внешние каналы уведомлений")
    ap.add_argument("--public-url", help="адрес панели для кнопки «Открыть в панели» в чатах")
    a = ap.parse_args()

    specs = a.source or ["synthetic", "synthetic:30"]
    if a.backend == "mock" and any(not s.startswith("synthetic") for s in specs):
        ap.error("backend mock работает только с источником synthetic; для видео задайте --backend onnx|linq")
    if a.backend != "mock" and not a.model:
        ap.error("для onnx и linq нужен --model")

    logger = configure_logging()
    logger.info("service_starting backend=%s cameras=%s host=%s port=%s",
                a.backend, len(specs), a.host, a.port)
    det = make_detector(a.backend, a.model, a.classes.split(",") if a.classes else None)
    store, zones, hub = EventStore(), ZoneStore(), Hub()
    enterprise = EnterpriseConfig()
    cams, workers = [], []
    for i, spec in enumerate(specs, 1):
        name = f"cam{i}"
        if spec.startswith("synthetic") and not zones.has(name):
            zones.set(name, [{"name": "Зона погрузчика", "points": sources.DEFAULT_ZONE}])
        w = CameraWorker(name, sources.open_source(spec), det, store, hub, zones, enterprise)
        cams.append({"id": name, "source": spec, "workshop": enterprise.workshop_for(name)})
        workers.append(w)
    notifier = Notifier(store, hub) if a.no_notifications else from_env(store, hub)
    if a.public_url and not a.no_notifications:
        notifier.public_url = a.public_url
    notifier.start()
    for w in workers:
        w.start()
    srv = serve(a.port, store, hub, zones, cams, det, host=a.host, notifier=notifier, enterprise=enterprise)
    if a.no_notifications:
        logger.info("external_notifications=disabled")
    else:
        logger.info("notification_channels=%s", ",".join(notifier.clients) or "not_configured")
    logger.info("service_ready url=http://localhost:%s backend=%s cameras=%s",
                a.port, det.name, len(cams))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        notifier.stop()
        for w in workers:
            w.stop()
        for w in workers:
            w.join(timeout=5)
            if w.is_alive():
                logger.warning("camera=%s did_not_stop_within_timeout", w.cam)
        logger.info("service_stopped")
        shutdown_logging()


if __name__ == "__main__":
    main()
