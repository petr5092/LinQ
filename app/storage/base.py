from abc import ABC, abstractmethod
from typing import Union
import numpy as np


class BaseStorageProvider(ABC):
    """
    Абстрактный интерфейс провайдера хранилища стоп-кадров инцидентов.
    """

    def save_snapshot_key(self, image_data, incident_id: str, camera_id: str) -> str:
        """Save evidence and return its durable object key, not an expiring URL."""
        raise NotImplementedError('Storage must implement durable snapshot keys')

    @abstractmethod
    def save_snapshot(
        self,
        image_data: Union[np.ndarray, bytes],
        incident_id: str,
        camera_id: str
    ) -> str:
        """
        Сохраняет изображение инцидента в хранилище.

        :param image_data: BGR-кадр numpy (OpenCV) или сырые байты JPEG
        :param incident_id: Уникальный идентификатор инцидента
        :param camera_id: Идентификатор камеры
        :return: Доступный URL или относительный путь к снапшоту
        """
        pass

    @abstractmethod
    def get_snapshot_url(self, file_key: str) -> str:
        """
        Возвращает публичный URL или Presigned URL для скачивания/просмотра.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Проверка доступности хранилища.
        """
        pass
