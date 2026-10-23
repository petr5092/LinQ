import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings, BASE_DIR
from app.db.session import check_db_connection
from app.routes.api import api_router
from app.routes.websocket import router as ws_router
from app.seed import seed_database
from app.storage.factory import get_storage_provider

# Настройка логирования
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("linq_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения FastAPI:
    - Проверка подключения к БД
    - Инициализация файловых каталогов хранилища
    - Первичное наполнение справочниками (seed) при пустой БД
    """
    logger.info("=== Запуск LinQ Safety Guard Backend ===")
    logger.info(f"Режим отладки (DEBUG): {settings.DEBUG}")
    logger.info(f"Бэкенд инференса: {settings.INFERENCE_BACKEND}")
    logger.info(f"Тип хранилища снапшотов: {settings.STORAGE_TYPE}")
    logger.info(f"Подключение к БД: {settings.DATABASE_URL}")

    # Проверка базы данных
    if check_db_connection():
        logger.info("[DB] Подключение к базе данных успешно подтверждено.")
    else:
        logger.error("[DB] ВНИМАНИЕ: Ошибка проверки подключения к БД!")

    # Гарантируем создание локальной папки снапшотов
    snapshots_dir = BASE_DIR / "storage" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    # Проверка хранилища
    storage = get_storage_provider()
    if storage.health_check():
        logger.info(f"[Storage] Хранилище '{settings.STORAGE_TYPE}' готово к работе.")
    else:
        logger.warning(f"[Storage] Внимание: хранилище '{settings.STORAGE_TYPE}' не прошло проверку доступности.")

    # Автоматический сид базовых данных при первом старте
    try:
        seed_database()
    except Exception as e:
        logger.warning(f"[Seed] Предупреждение при проверке начальных данных: {e}")

    yield

    logger.info("=== Остановка LinQ Safety Guard Backend ===")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Комплексный сервис видеоаналитики и промышленной безопасности на базе LinQ TPU. "
        "REST API для операторского интерфейса, интеграции с CV Engine и WebSockets оповещений."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Настройка CORS для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтирование статических файлов снапшотов
snapshots_path = BASE_DIR / "storage" / "snapshots"
snapshots_path.mkdir(parents=True, exist_ok=True)
app.mount("/static/snapshots", StaticFiles(directory=str(snapshots_path)), name="snapshots")

# Монтирование собранного веб-интерфейса (SPA)
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/ui", StaticFiles(directory=str(frontend_dist), html=True), name="frontend-ui")

# Подключение маршрутов API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
# Алиас для прямого вызова /health на корневом уровне (стандарт k8s / docker probes)
from app.routes.health import router as health_router
app.include_router(health_router)

# Подключение WebSocket канала
app.include_router(ws_router)


@app.get("/", tags=["Root"])
def root():
    data = {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "health_url": f"{settings.API_V1_PREFIX}/health",
        "websocket_url": "/ws/events",
    }
    frontend_dist = BASE_DIR / "frontend" / "dist"
    if frontend_dist.exists():
        data["ui_url"] = "/ui"
    return data
