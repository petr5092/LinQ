import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Базовые директории
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT = str(BASE_DIR)
load_dotenv(BASE_DIR / ".env")

# Директории данных и стоп-кадров
DATA_DIR = os.environ.get("LINQ_DATA", os.path.join(ROOT, "data"))
SNAP_DIR = os.path.join(DATA_DIR, "snaps")

# Константы компьютерного зрения и параметров правил
CLASS_NAMES = ["person", "helmet", "no_helmet", "vest", "no_vest", "phone"]
INPUT_SIZE = 640
CONF_THR = 0.35
NMS_IOU = 0.5

RULE_PARAMS = {
    "fall":            {"confirm_s": 2.0, "aspect": 1.25, "still_s": 1.0},
    "restricted_zone": {"confirm_s": 1.5},
    "no_helmet":       {"confirm_s": 2.0, "mode": "negative"},
    "no_vest":         {"confirm_s": 2.0, "mode": "negative"},
    "phone":           {"confirm_s": 2.0},
}

ENGINE = {
    "gap_s": 2.0,
    "dedup_s": 20.0,
    "dedup_dist": 0.06,
}


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

    # База данных (PostgreSQL)
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'postgres')}@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'linq_safety')}"
        )
    )

    # Параметры пула подключений к БД
    DB_POOL_SIZE: int = Field(default_factory=lambda: int(os.getenv("DB_POOL_SIZE", "10")))
    DB_MAX_OVERFLOW: int = Field(default_factory=lambda: int(os.getenv("DB_MAX_OVERFLOW", "20")))
    DB_POOL_TIMEOUT: int = Field(default_factory=lambda: int(os.getenv("DB_POOL_TIMEOUT", "30")))

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

    # Камера и видеоисточник
    CAMERA_SOURCE: str = Field(
        default_factory=lambda: os.getenv("CAMERA_SOURCE", "storage/demo_videos/construction_safety.mp4")
    )
    CAMERA_NAME: str = Field(
        default_factory=lambda: os.getenv("CAMERA_NAME", "Xiaomi Smart Camera 3 Pro")
    )

    # Telegram & Внешние уведомления
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default_factory=lambda: os.getenv("LINQ_TG_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN"))
    TELEGRAM_API_BASE: str = Field(default_factory=lambda: os.getenv("LINQ_TG_API") or os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org"))
    PUBLIC_DASHBOARD_URL: Optional[str] = Field(default_factory=lambda: os.getenv("PUBLIC_DASHBOARD_URL") or os.getenv("LINQ_PUBLIC_URL", "http://localhost:3000"))


settings = Settings()
