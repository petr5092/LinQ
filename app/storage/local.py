import os
from datetime import datetime, timezone
from typing import Union
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


class LocalStorageProvider(BaseStorageProvider):
    """
    Провайдер локального хранилища (файловая система).
    """

    def __init__(self, base_dir: str = "storage/snapshots", url_prefix: str = "/static/snapshots", jpeg_quality: int = 80):
        self.base_dir = os.path.abspath(base_dir)
        self.url_prefix = url_prefix.rstrip("/")
        self.jpeg_quality = jpeg_quality
        os.makedirs(self.base_dir, exist_ok=True)

    def save_snapshot(
        self,
        image_data: Union[np.ndarray, bytes],
        incident_id: str,
        camera_id: str
    ) -> str:
        date_folder = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        target_dir = os.path.join(self.base_dir, date_folder)
        os.makedirs(target_dir, exist_ok=True)

        filename = f"inc_{incident_id}_{camera_id}.jpg"
        file_path = os.path.join(target_dir, filename)

        if isinstance(image_data, np.ndarray):
            if cv2 is not None:
                # cv2.imencode + python open() гарантирует корректную запись в пути с кириллицей на Windows
                is_success, buf = cv2.imencode(".jpg", image_data, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
                if is_success:
                    with open(file_path, "wb") as f:
                        f.write(buf.tobytes())
                else:
                    cv2.imwrite(file_path, image_data, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            elif Image is not None:
                img = Image.fromarray(image_data)
                img.save(file_path, "JPEG", quality=self.jpeg_quality)
            else:
                raise ImportError("Не найдены библиотеки cv2 или PIL для сохранения numpy array")
        elif isinstance(image_data, (bytes, bytearray)):
            with open(file_path, "wb") as f:
                f.write(image_data)
        else:
            raise ValueError(f"Неподдерживаемый тип данных изображения: {type(image_data)}")

        # Относительный ключ для БД и отдачи через FastAPI
        rel_key = f"{date_folder}/{filename}"
        return self.get_snapshot_url(rel_key)

    def get_snapshot_url(self, file_key: str) -> str:
        clean_key = file_key.lstrip("/")
        return f"{self.url_prefix}/{clean_key}"

    def health_check(self) -> bool:
        return os.path.exists(self.base_dir) and os.access(self.base_dir, os.W_OK)
