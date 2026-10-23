import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings, BASE_DIR

# Если используется SQLite, гарантируем существование директории для файла базы данных
database_url = settings.DATABASE_URL
connect_args = {}

if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    
    # Извлекаем путь к файлу базы данных и создаем папку при необходимости
    db_file_part = database_url.replace("sqlite:///", "").replace("sqlite://", "")
    if db_file_part and db_file_part != ":memory:":
        # Обработка относительного пути от корня проекта
        db_path = BASE_DIR / db_file_part if not os.path.isabs(db_file_part) else Path(db_file_part)
        db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)


# Для SQLite включаем принудительную проверку внешних ключей
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if database_url.startswith("sqlite"):
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
