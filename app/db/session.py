import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings, BASE_DIR

database_url = settings.DATABASE_URL
engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False,
}

if database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    # Извлекаем путь к файлу базы данных и создаем папку при необходимости
    db_file_part = database_url.replace("sqlite:///", "").replace("sqlite://", "")
    if db_file_part and db_file_part != ":memory:":
        db_path = BASE_DIR / db_file_part if not os.path.isabs(db_file_part) else Path(db_file_part)
        db_path.parent.mkdir(parents=True, exist_ok=True)
elif database_url.startswith("postgresql"):
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
    engine_kwargs["pool_recycle"] = 3600

engine = create_engine(database_url, **engine_kwargs)


# Для SQLite включаем принудительную проверку внешних ключей
if database_url.startswith("sqlite"):
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency для получения сессии базы данных с гарантированным закрытием.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Проверка доступности базы данных (healthcheck).
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[Database] Health check failed: {e}")
        return False
