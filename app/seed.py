"""Первичное наполнение базы справочниками площадок, зон и камер."""
from datetime import datetime
from sqlalchemy import select, delete
from app.db.session import SessionLocal
from app.db.models.site import Site, Workshop, Zone
from app.db.models.camera import Camera

SEED_SITES = [
    {
        "id": "north",
        "name": "Завод «Северный»",
        "subtitle": "Основная площадка",
        "workshops": [
            {"name": "Корпус А", "zones": ["Цех № 1"]},
        ],
    },
]

SEED_CAMERAS = [
    {"id": "CAM-01", "name": "Xiaomi 360° 3 Pro (Сборочный участок)", "zone": "Цех № 1", "workshop": "Корпус А", "site_id": "north", "image_placeholder": "construction", "rtsp_url": "rtsp://127.0.0.1:8554/xiaomi_cam", "online": True},
    # Integration/demo radiometric camera. The replay utility sends open CSV frames to it.
    {"id": "THERMAL-OSF-TEST", "name": "Тепловизор · тест OSF", "zone": "Цех № 1", "workshop": "Корпус А", "site_id": "north", "image_placeholder": "workshop", "online": False, "fps": 1.0, "camera_type": "thermal"},
]

def seed_database():
    from app.db.base import Base
    from app.db.session import engine
    Base.metadata.create_all(bind=engine)
    """Заполняет справочники площадок и камер, не создавая вымышленные инциденты."""
    db = SessionLocal()
    try:
        # 1. Проверяем наличие площадок
        existing_sites = db.scalar(select(Site))
        if not existing_sites:
            print("[Seed] Заполнение базы данных площадками и зонами...")
            for s_data in SEED_SITES:
                site = Site(id=s_data["id"], name=s_data["name"], subtitle=s_data["subtitle"])
                db.add(site)
                db.flush()

                for w_data in s_data["workshops"]:
                    workshop = Workshop(site_id=site.id, name=w_data["name"])
                    db.add(workshop)
                    db.flush()

                    for zone_name in w_data["zones"]:
                        zone = Zone(workshop_id=workshop.id, name=zone_name)
                        db.add(zone)

            db.commit()
            print("[Seed] Площадки и зоны успешно созданы.")

        # 2. Add missing demo cameras without overwriting existing operator settings.
        # This also makes the radiometric integration visible in databases that
        # already contain the original visible CAM-01.
        seed_ids = {c["id"] for c in SEED_CAMERAS}
        deleted = db.execute(delete(Camera).where(Camera.id.not_in(seed_ids)))
        if deleted.rowcount:
            db.commit()
            print(f"[Seed] Удалены устаревшие тестовые камеры: {deleted.rowcount}")

        added_cameras = False
        for c_data in SEED_CAMERAS:
            if db.get(Camera, c_data["id"]):
                continue
            if not db.get(Site, c_data["site_id"]):
                continue
            db.add(Camera(
                id=c_data["id"],
                name=c_data["name"],
                zone=c_data["zone"],
                workshop=c_data["workshop"],
                site_id=c_data["site_id"],
                image_placeholder=c_data["image_placeholder"],
                rtsp_url=c_data.get("rtsp_url"),
                camera_type=c_data.get("camera_type", "visible"),
                online=c_data["online"],
                fps=c_data.get("fps", 25.0),
                last_heartbeat=datetime.utcnow(),
            ))
            added_cameras = True
        if added_cameras:
            db.commit()
            print("[Seed] Отсутствующие демонстрационные камеры созданы.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
