from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.db.models.site import Site, Workshop, Zone
from app.schemas.site import SiteRead, SiteCreate, ZoneRead, ZoneCreate
from app.schemas.common import StatusResponse

router = APIRouter(prefix="/sites", tags=["Sites & Zones"])


@router.get("", response_model=List[SiteRead])
def list_sites(db: Session = Depends(get_db)):
    """Получение всех промышленных площадок с цехами и зонами."""
    stmt = (
        select(Site)
        .options(
            selectinload(Site.workshops).selectinload(Workshop.zones)
        )
    )
    sites = db.scalars(stmt).all()
    return sites


@router.get("/{site_id}", response_model=SiteRead)
def get_site(site_id: str, db: Session = Depends(get_db)):
    """Получение конкретной площадки по ее ID."""
    stmt = (
        select(Site)
        .where(Site.id == site_id)
        .options(
            selectinload(Site.workshops).selectinload(Workshop.zones)
        )
    )
    site = db.scalar(stmt)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Площадка не найдена")
    return site


@router.post("", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
def create_site(site_in: SiteCreate, db: Session = Depends(get_db)):
    """Регистрация новой производственной площадки."""
    existing = db.scalar(select(Site).where(Site.id == site_in.id))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Площадка с идентификатором {site_in.id} уже существует"
        )
    site = Site(
        id=site_in.id,
        name=site_in.name,
        subtitle=site_in.subtitle,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.put("/zones/{zone_id}/polygon", response_model=StatusResponse)
def update_zone_polygon(zone_id: int, polygon_coords: dict, db: Session = Depends(get_db)):
    """
    Обновление координат полигона зоны (редактирование зоны на интерактивном холсте).
    """
    zone = db.scalar(select(Zone).where(Zone.id == zone_id))
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона не найдена")

    zone.polygon_coordinates = polygon_coords
    db.commit()
    return StatusResponse(message="Полигон зоны успешно обновлен")
