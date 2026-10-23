from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Site(Base, TimestampMixin):
    """Модель промышленной площадки предприятия (завода/комплекса)."""
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 'north', 'south', 'east'
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 'Завод «Северный»'
    subtitle: Mapped[str] = mapped_column(String(100), default="")  # 'Основная площадка'

    workshops: Mapped[List["Workshop"]] = relationship(
        "Workshop", back_populates="site", cascade="all, delete-orphan", order_by="Workshop.id"
    )
    cameras: Mapped[List["Camera"]] = relationship(
        "Camera", back_populates="site", cascade="all, delete-orphan"
    )
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident", back_populates="site", cascade="all, delete-orphan"
    )


class Workshop(Base, TimestampMixin):
    """Корпус или цеховая структура внутри площадки."""
    __tablename__ = "workshops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 'Корпус А'

    site: Mapped["Site"] = relationship("Site", back_populates="workshops")
    zones: Mapped[List["Zone"]] = relationship(
        "Zone", back_populates="workshop", cascade="all, delete-orphan", order_by="Zone.id"
    )


class Zone(Base, TimestampMixin):
    """Рабочая или опасная зона внутри цеха."""
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workshop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # 'Цех № 1'
    polygon_coordinates: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rules: Mapped[list] = mapped_column(JSON, default=list)  # Список активных правил ТБ

    workshop: Mapped["Workshop"] = relationship("Workshop", back_populates="zones")
