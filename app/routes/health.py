from datetime import datetime
from fastapi import APIRouter
from app.config import settings
from app.db.session import check_db_connection
from app.storage.factory import get_storage_provider
from app.schemas.health import HealthCheckResponse

router = APIRouter(prefix="", tags=["Health"])


@router.get("/health", response_model=HealthCheckResponse)
def healthcheck():
    """
    Комплексная проверка работоспособности системы:
    - Доступность базы данных (SQLite/PostgreSQL)
    - Статус хранилища снапшотов (Local FS / S3)
    - Активный бэкенд инференса (LinQ TPU / ONNX CPU)
    """
    storage = get_storage_provider()
    db_ok = check_db_connection()
    storage_ok = storage.health_check()

    status = "healthy"
    if not db_ok or not storage_ok:
        status = "degraded" if (db_ok or storage_ok) else "unhealthy"

    return HealthCheckResponse(
        status=status,
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        database=db_ok,
        storage={
            "type": settings.STORAGE_TYPE,
            "healthy": storage_ok,
        },
        inference_backend=settings.INFERENCE_BACKEND,
        timestamp=datetime.utcnow()
    )
