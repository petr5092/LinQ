from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CameraBase(BaseModel):
    name: str = Field(..., max_length=100, description="Название камеры")
    zone: str = Field(..., max_length=100, description="Зона размещения")
    workshop: str = Field(..., max_length=100, description="Цех / корпус")
    site_id: str = Field(..., max_length=50, description="ID площадки (north/south/east)")
    rtsp_url: Optional[str] = Field(None, description="RTSP видеопоток")
    camera_type: str = Field("visible", pattern="^(visible|thermal)$", description="visible | thermal")
    image_placeholder: str = Field("workshop", description="Тип ракурса/фонового изображения")
    online: bool = Field(True, description="Статус подключения камеры")
    fps: Optional[float] = Field(25.0, description="Частота кадров")


class CameraCreate(CameraBase):
    id: str = Field(..., max_length=50, description="Уникальный идентификатор (например 'CAM-01')")


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    zone: Optional[str] = None
    workshop: Optional[str] = None
    rtsp_url: Optional[str] = None
    camera_type: Optional[str] = Field(None, pattern="^(visible|thermal)$")
    image_placeholder: Optional[str] = None
    online: Optional[bool] = None
    fps: Optional[float] = None


class CameraRead(CameraBase):
    id: str
    last_heartbeat: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
