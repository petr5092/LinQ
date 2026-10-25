from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ThermalReading(Base):
    """Low-rate per-zone temperature history; raw radiometric matrices are not stored."""
    __tablename__ = "thermal_readings"
    __table_args__ = (
        Index("ix_thermal_reading_camera_zone_time", "camera_id", "zone_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[str] = mapped_column(String(100), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    min_temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    mean_temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    max_temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_c: Mapped[float] = mapped_column(Float, nullable=False)
    hot_pixels: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alarm: Mapped[bool] = mapped_column(nullable=False, default=False)
