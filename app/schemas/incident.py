from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class EmployeeInfo(BaseModel):
    name: str = ""
    role: str = ""
    number: str = ""
    access: str = ""


class ContactInfo(BaseModel):
    name: str = ""
    role: str = ""
    radio: str = ""
    phone: str = ""


class IncidentBase(BaseModel):
    site_id: str = Field(..., max_length=50)
    camera_id: str = Field(..., max_length=50)
    zone: str = Field(..., max_length=100)
    title: str = Field(..., max_length=200)
    time: str = Field(..., description="Время фиксации в формате HH:MM:SS")
    severity: str = Field("warning", description="critical | warning | info")
    type: str = Field("person", description="person | environment | access")
    description: str = ""
    action: str = ""
    image_key: str = Field("", description="Путь к снапшоту в хранилище")
    status: str = Field("new", description="new | working | resolved | dismissed")
    box: Optional[List[float]] = Field(None, description="Координаты детекции [x, y, w, h]")

    # Сведения о сотруднике
    employee_name: Optional[str] = None
    employee_role: Optional[str] = None
    employee_number: Optional[str] = None
    employee_access: Optional[str] = None

    # Контактное лицо
    contact_name: Optional[str] = None
    contact_role: Optional[str] = None
    contact_radio: Optional[str] = None
    contact_phone: Optional[str] = None

    # Дополнительные поля детектора
    track_id: Optional[int] = None
    confidence: Optional[float] = None
    is_verified: bool = False


class IncidentCreate(IncidentBase):
    id: Optional[str] = Field(None, description="Опциональный ID (генерируется при отсутствии)")


class IncidentUpdateStatus(BaseModel):
    status: str = Field(..., description="new | working | resolved | dismissed")
    comment: Optional[str] = None


class IncidentRead(IncidentBase):
    id: str
    snapshot_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Вычисляемые поля для совместимости с React фронтендом
    employee: Optional[EmployeeInfo] = None
    contact: Optional[ContactInfo] = None

    model_config = ConfigDict(from_attributes=True)
