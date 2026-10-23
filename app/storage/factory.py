import os
from typing import Optional
from app.storage.base import BaseStorageProvider
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider


def get_storage_provider() -> BaseStorageProvider:
    """
    Фабрика создания провайдера хранилища на основе переменных окружения.
    """
    storage_type = os.getenv("STORAGE_TYPE", "local").lower().strip()

    if storage_type == "s3":
        endpoint_url = os.getenv("S3_ENDPOINT_URL", "https://storage.yandexcloud.net")
        access_key = os.getenv("S3_ACCESS_KEY_ID", "")
        secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "")
        bucket_name = os.getenv("S3_BUCKET_NAME", "linq-safety-snapshots")
        region_name = os.getenv("S3_REGION_NAME", "ru-central1")
        public_url_prefix = os.getenv("S3_PUBLIC_URL_PREFIX", None)

        if not access_key or not secret_key:
            print("[StorageFactory] Внимание: S3 ключи не найдены, переключение на локальное хранилище.")
            return LocalStorageProvider()

        try:
            return S3StorageProvider(
                endpoint_url=endpoint_url,
                access_key=access_key,
                secret_key=secret_key,
                bucket_name=bucket_name,
                region_name=region_name,
                public_url_prefix=public_url_prefix
            )
        except Exception as e:
            print(f"[StorageFactory] Ошибка инициализации S3 ({e}), откат на LocalStorageProvider.")
            return LocalStorageProvider()

    return LocalStorageProvider()
