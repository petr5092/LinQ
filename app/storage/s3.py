import io
import os
from datetime import datetime
from typing import Union, Optional
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import Image
except ImportError:
    Image = None

from app.storage.base import BaseStorageProvider

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None


class S3StorageProvider(BaseStorageProvider):
    """
    Провайдер объектного хранилища по S3-протоколу (MinIO / Yandex Cloud Object Storage / AWS).
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region_name: str = "ru-central1",
        presigned_expiry_seconds: int = 86400,
        jpeg_quality: int = 80,
        public_url_prefix: Optional[str] = None
    ):
        if boto3 is None:
            raise ImportError("Пакет 'boto3' не установлен. Установите его: pip install boto3")

        self.endpoint_url = endpoint_url
        self.bucket_name = bucket_name
        self.presigned_expiry = presigned_expiry_seconds
        self.jpeg_quality = jpeg_quality
        self.public_url_prefix = public_url_prefix

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
        )

        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
            except Exception:
                # В облаках бакет может уже существовать с ограниченными правами HeadBucket
                pass

    def save_snapshot(
        self,
        image_data: Union[np.ndarray, bytes],
        incident_id: str,
        camera_id: str
    ) -> str:
        return self.get_snapshot_url(self.save_snapshot_key(image_data, incident_id, camera_id))

    def save_snapshot_key(self, image_data, incident_id: str, camera_id: str) -> str:
        date_folder = datetime.utcnow().strftime("%Y-%m-%d")
        file_key = f"snapshots/{date_folder}/inc_{incident_id}_{camera_id}.jpg"

        if isinstance(image_data, np.ndarray):
            if cv2 is not None:
                success, buffer = cv2.imencode(".jpg", image_data, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
                if not success:
                    raise ValueError("Не удалось закодировать кадр в JPEG через cv2")
                data_bytes = buffer.tobytes()
            elif Image is not None:
                buf = io.BytesIO()
                img = Image.fromarray(image_data)
                img.save(buf, format="JPEG", quality=self.jpeg_quality)
                data_bytes = buf.getvalue()
            else:
                raise ImportError("Не найдены cv2 или PIL для кодирования изображения")
        elif isinstance(image_data, (bytes, bytearray)):
            data_bytes = image_data
        else:
            raise ValueError(f"Неподдерживаемый тип данных изображения: {type(image_data)}")

        self.client.put_object(
            Bucket=self.bucket_name,
            Key=file_key,
            Body=io.BytesIO(data_bytes),
            ContentType="image/jpeg"
        )

        return file_key

    def get_snapshot_url(self, file_key: str) -> str:
        # Если задан прямой публичный URL или CDN
        if self.public_url_prefix:
            return f"{self.public_url_prefix.rstrip('/')}/{file_key.lstrip('/')}"

        # Иначе генерируем безопасный Presigned URL
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": file_key},
                ExpiresIn=self.presigned_expiry
            )
        except Exception:
            return f"{self.endpoint_url}/{self.bucket_name}/{file_key}"

    def health_check(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception:
            return False
