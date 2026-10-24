"""
Единая точка входа для запуска LinQ Safety Guard:
    python run.py                                     # Запуск полного FastAPI сервера
    python run.py --backend onnx --model best.onnx    # Запуск CV воркера с локальной ONNX моделью
    python run.py --backend linq --model program.tpu  # Запуск CV воркера на LinQ TPU
    python run.py --standalone                        # Легковесное демо на встроенном сервере
"""

from __future__ import annotations

import argparse
import sys
import uvicorn

from run_worker import main as worker_main


def standalone_main():
    from app import config, sources
    from app.detector import make_detector
    from app.enterprise import EnterpriseConfig
    from app.hub import Hub
    from app.logging_config import configure_logging, shutdown_logging
    from app.notify.core import Notifier, from_env
    from app.pipeline import CameraWorker
    from app.server import serve
    from app.store import EventStore, ZoneStore

    ap = argparse.ArgumentParser(description="Standalone LinQ Safety Demo")
    ap.add_argument("--source", action="append", help="synthetic | synthetic:30 | demo | файл | rtsp://…")
    ap.add_argument("--demo-video", action="store_true", help="использовать видео из storage/demo_videos/construction_safety.mp4")
    ap.add_argument("--backend", default="mock", choices=["mock", "onnx", "linq"])
    ap.add_argument("--model", help="путь к модели")
    ap.add_argument("--classes", help="имена классов через запятую")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-notifications", action="store_true")
    ap.add_argument("--public-url", help="адрес панели")
    ap.add_argument("--standalone", action="store_true")
    a, _ = ap.parse_known_args()

    if a.demo_video:
        specs = [os.path.join("storage", "demo_videos", "construction_safety.mp4")]
    else:
        specs = a.source or ["synthetic", "synthetic:30"]
    logger = configure_logging()
    logger.info("service_starting standalone backend=%s cameras=%s", a.backend, len(specs))
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
    logger.info("service_ready url=http://%s:%s backend=%s cameras=%s", a.host, a.port, det.name, len(cams))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        notifier.stop()
        for w in workers:
            w.stop()
            w.join(timeout=5)
        logger.info("service_stopped")
        shutdown_logging()


if __name__ == "__main__":
    if "--standalone" in sys.argv:
        standalone_main()
    elif len(sys.argv) > 1 and any(arg in sys.argv for arg in ("--source", "--backend", "--model", "--web")):
        worker_main()
    else:
        from app.main import app
        from app.config import settings
        print(f"=== Запуск LinQ Safety Guard API на http://{settings.HOST}:{settings.PORT} ===")
        uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
