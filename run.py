"""
Единая точка входа для запуска LinQ Safety Guard:
    python run.py                                     # Только FastAPI; CV запускается отдельно
    python run.py --backend onnx --model best.onnx    # Запуск с локальной ONNX моделью
    python run.py --backend linq --model program.tpu  # Запуск на аппаратном чипе LinQ TPU
"""

from __future__ import annotations

import argparse
import sys
import uvicorn

from run_worker import main as worker_main


if __name__ == "__main__":
    # Если переданы аргументы командной строки воркера — запускаем воркер
    if len(sys.argv) > 1 and any(arg in sys.argv for arg in ("--source", "--backend", "--model", "--web")):
        raise SystemExit(worker_main())
    else:
        # По умолчанию запускаем только FastAPI сервер.
        from app.main import app
        from app.config import settings
        print(f"=== Запуск LinQ Safety Guard API на http://{settings.HOST}:{settings.PORT} ===")
        uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
