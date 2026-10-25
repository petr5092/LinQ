from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Camera(Base, TimestampMixin):
    """Модель видеокамеры наблюдения на объекте."""
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 'CAM-01'
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 'Сборочный участок'
    zone: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # 'Цех № 1'
    workshop: Mapped[str] = mapped_column(String(100), nullable=False)  # 'Корпус А'
    site_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rtsp_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    camera_type: Mapped[str] = mapped_column(String(20), default="visible", nullable=False)
    image_placeholder: Mapped[str] = mapped_column(String(50), default="workshop")
    online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fps: Mapped[Optional[float]] = mapped_column(Float, default=25.0)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    site: Mapped["Site"] = relationship("Site", back_populates="cameras")
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident", back_populates="camera", cascade="all, delete-orphan", order_by="Incident.created_at.desc()"
    )
