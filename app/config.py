import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Загружаем переменные из .env в корне проекта LinQproject
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseModel):
    # Метаданные приложения
    PROJECT_NAME: str = "LinQ Safety Guard"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = Field(default_factory=lambda: os.getenv("DEBUG", "True").lower() in ("true", "1", "yes"))

    # Сервер
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*",
    ]

    # База данных (SQLite по умолчанию)
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./storage/db.sqlite3")
    )

    # Хранилище стоп-кадров нарушений
    STORAGE_TYPE: str = Field(default_factory=lambda: os.getenv("STORAGE_TYPE", "local").lower())
    LOCAL_SNAPSHOTS_DIR: Path = BASE_DIR / "storage" / "snapshots"
    S3_ENDPOINT_URL: str = Field(default_factory=lambda: os.getenv("S3_ENDPOINT_URL", "https://storage.yandexcloud.net"))
    S3_ACCESS_KEY_ID: str = Field(default_factory=lambda: os.getenv("S3_ACCESS_KEY_ID", ""))
    S3_SECRET_ACCESS_KEY: str = Field(default_factory=lambda: os.getenv("S3_SECRET_ACCESS_KEY", ""))
    S3_BUCKET_NAME: str = Field(default_factory=lambda: os.getenv("S3_BUCKET_NAME", "linq-safety-snapshots"))
    S3_REGION_NAME: str = Field(default_factory=lambda: os.getenv("S3_REGION_NAME", "ru-central1"))
    S3_PUBLIC_URL_PREFIX: Optional[str] = Field(default_factory=lambda: os.getenv("S3_PUBLIC_URL_PREFIX") or None)

    # Инференс & HAL
    INFERENCE_BACKEND: str = Field(default_factory=lambda: os.getenv("INFERENCE_BACKEND", "ONNX_CPU"))
    ONNX_MODEL_PATH: str = Field(default_factory=lambda: os.getenv("ONNX_MODEL_PATH", "models/onnx/yolov8n_safety_640.onnx"))
    TPU_MODEL_PATH: str = Field(default_factory=lambda: os.getenv("TPU_MODEL_PATH", "models/tpu/yolov8n_b1_o1_h1m.tpu"))

    # Пороги и правила
    CONFIDENCE_THRESHOLD: float = Field(default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.45")))
    IOU_THRESHOLD: float = Field(default_factory=lambda: float(os.getenv("IOU_THRESHOLD", "0.45")))
    DEBOUNCE_FRAMES: int = Field(default_factory=lambda: int(os.getenv("DEBOUNCE_FRAMES", "15")))
    COOLDOWN_SECONDS: int = Field(default_factory=lambda: int(os.getenv("COOLDOWN_SECONDS", "300")))


settings = Settings()
