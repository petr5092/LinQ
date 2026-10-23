from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ZoneBase(BaseModel):
    name: str = Field(..., max_length=100, description="Название зоны")
    polygon_coordinates: Optional[dict] = Field(None, description="Координаты полигона зоны")
    rules: List[str] = Field(default_factory=list, description="Правила ТБ в зоне")


class ZoneCreate(ZoneBase):
    workshop_id: int


class ZoneRead(ZoneBase):
    id: int
    workshop_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkshopBase(BaseModel):
    name: str = Field(..., max_length=100)


class WorkshopCreate(WorkshopBase):
    site_id: str


class WorkshopRead(WorkshopBase):
    id: int
    site_id: str
    zones: List[ZoneRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SiteBase(BaseModel):
    id: str = Field(..., max_length=50, description="Идентификатор площадки (например 'north')")
    name: str = Field(..., max_length=100, description="Название (например 'Завод «Северный»')")
    subtitle: str = Field("", max_length=100, description="Подзаголовок (например 'Основная площадка')")


class SiteCreate(SiteBase):
    pass


class SiteRead(SiteBase):
    workshops: List[WorkshopRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
