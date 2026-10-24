import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import make_url

from app.config import settings, BASE_DIR
from app.db.session import check_db_connection
from app.routes.api import api_router
from app.routes.websocket import router as ws_router
from app.seed import seed_database
from app.services.notifications import notification_manager
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
    - Запуск менеджера фоновых уведомлений
    """
    logger.info("=== Запуск LinQ Safety Guard Backend ===")
    logger.info(f"Режим отладки (DEBUG): {settings.DEBUG}")
    logger.info(f"Бэкенд инференса: {settings.INFERENCE_BACKEND}")
    logger.info(f"Тип хранилища снапшотов: {settings.STORAGE_TYPE}")
    database_url = make_url(settings.DATABASE_URL).render_as_string(hide_password=True)
    logger.info(f"Подключение к БД: {database_url}")

    # Проверка базы данных
    if check_db_connection():
        logger.info("[DB] Подключение к базе данных успешно подтверждено.")
    else:
        logger.error("[DB] ВНИМАНИЕ: Ошибка проверки подключения к БД!")

    # Гарантируем создание локальной папки снапшотов и данных
    snapshots_dir = BASE_DIR / "storage" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

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

    # Запуск фонового менеджера внешних уведомлений
    try:
        notification_manager.start()
    except Exception as e:
        logger.warning(f"[Notify] Предупреждение при запуске службы оповещений: {e}")

    # Запуск фонового CV-воркера для онлайн-камеры CAM-01
    import threading
    stop_cv_event = threading.Event()
    demo_video_path = str(BASE_DIR / "storage" / "demo_videos" / "construction_safety.mp4")
    if Path(demo_video_path).exists():
        try:
            from run_worker import run_camera_worker
            cv_thread = threading.Thread(
                target=run_camera_worker,
                args=(
                    "CAM-01",
                    demo_video_path,
                    settings.INFERENCE_BACKEND.lower(),
                    settings.ONNX_MODEL_PATH,
                    stop_cv_event,
                ),
                daemon=True,
                name="cv_worker_CAM-01",
            )
            cv_thread.start()
            logger.info("[CV Worker] Видеоаналитика нейросети для CAM-01 запущена в реальном времени.")
        except Exception as e:
            logger.warning(f"[CV Worker] Ошибка запуска фонового воркера CAM-01: {e}")

    yield

    logger.info("=== Остановка LinQ Safety Guard Backend ===")
    try:
        stop_cv_event.set()
    except Exception:
        pass
    try:
        notification_manager.stop()
    except Exception:
        pass


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

# Монтирование демонстрационных видеозаписей
demo_videos_path = BASE_DIR / "storage" / "demo_videos"
demo_videos_path.mkdir(parents=True, exist_ok=True)
app.mount("/static/videos", StaticFiles(directory=str(demo_videos_path)), name="demo-videos")
app.mount("/videos", StaticFiles(directory=str(demo_videos_path)), name="videos")

# Монтирование графических ракурсов камер
images_path = BASE_DIR / "frontend" / "public" / "images"
if images_path.exists():
    app.mount("/images", StaticFiles(directory=str(images_path)), name="images")

# Монтирование собранного веб-интерфейса (SPA)
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/ui", StaticFiles(directory=str(frontend_dist), html=True), name="frontend-ui")
    assets_path = frontend_dist / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="frontend-assets")

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
        "demo_video": "/videos/construction_safety.mp4",
    }
    frontend_dist = BASE_DIR / "frontend" / "dist"
    if frontend_dist.exists():
        data["ui_url"] = "/ui"
    return data
