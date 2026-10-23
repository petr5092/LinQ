from typing import Optional, List
from sqlalchemy import String, Integer, Float, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Incident(Base, TimestampMixin):
    """
    Модель зафиксированного инцидента / события нарушения ТБ и ОТ.
    """
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 'TK-1048'
    site_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    camera_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    time: Mapped[str] = mapped_column(String(20), nullable=False)  # '14:32:08'
    
    # Severity: critical, warning, info
    severity: Mapped[str] = mapped_column(String(20), default="warning", nullable=False, index=True)
    
    # Type: person, environment, access
    type: Mapped[str] = mapped_column(String(30), default="person", nullable=False, index=True)
    
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    
    # Относительный путь к сохраненному кадру в LocalStorage или ключ в S3
    image_key: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    
    # Status: new, working, resolved, dismissed
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False, index=True)
    
    # Bounding box [x, y, w, h] (в процентах 0..100 или пикселях)
    box: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Привязка сотрудника (при интеграции со СКУД)
    employee_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employee_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employee_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    employee_access: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Контактное лицо для реагирования
    contact_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_radio: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Метаданные CV-трекинга
    track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    site: Mapped["Site"] = relationship("Site", back_populates="incidents")
    camera: Mapped["Camera"] = relationship("Camera", back_populates="incidents")
