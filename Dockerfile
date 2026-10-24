# syntax=docker/dockerfile:1
FROM python:3.10-slim

# Системные зависимости для OpenCV, видеопотоков и сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка зависимостей Python с кэшированием слоев
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода и вспомогательных модулей
COPY app/ ./app/
COPY engine/ ./engine/
COPY linq_tools/ ./linq_tools/
COPY models/ ./models/
COPY storage/ ./storage/
COPY run.py run_worker.py linq_adapter.py alembic.ini ./
COPY alembic/ ./alembic/

# Создание необходимых каталогов для стоп-кадров и логов
RUN mkdir -p storage/snapshots storage/demo_videos data/snaps

# Переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    INFERENCE_BACKEND=ONNX_CPU \
    ONNX_MODEL_PATH=models/onnx/safety_yolov8n.onnx

EXPOSE 8000

# Запуск единого сервиса API и видеоаналитики
CMD ["python", "run.py"]
