"""Первичное наполнение базы справочниками площадок, зон и камер."""
from datetime import datetime
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models.site import Site, Workshop, Zone
from app.db.models.camera import Camera

SEED_SITES = [
    {
        "id": "north",
        "name": "Завод «Северный»",
        "subtitle": "Основная площадка",
        "workshops": [
            {"name": "Корпус А", "zones": ["Цех № 1", "Окрасочный участок"]},
            {"name": "Корпус Б", "zones": ["Склад", "Погрузочная зона"]},
            {"name": "Периметр", "zones": ["Проходная", "Периметр", "Высотные работы"]},
        ],
    },
    {
        "id": "south",
        "name": "Южная площадка",
        "subtitle": "Логистический терминал",
        "workshops": [
            {"name": "Терминал", "zones": ["Зона разгрузки", "Конвейерная линия"]},
            {"name": "КПП", "zones": ["Южные ворота", "Парковка"]},
        ],
    },
    {
        "id": "east",
        "name": "Восточная площадка",
        "subtitle": "Строительный участок",
        "workshops": [
            {"name": "Монтажный участок", "zones": ["Котлован", "Монтажная зона"]},
            {"name": "Склад стройматериалов", "zones": ["Склад стройматериалов", "Бытовой городок"]},
        ],
    },
]

SEED_CAMERAS = [
    {"id": "CAM-01", "name": "Xiaomi 360° 3 Pro (Сборочный участок)", "zone": "Цех № 1", "workshop": "Корпус А", "site_id": "north", "image_placeholder": "construction", "rtsp_url": "rtsp://127.0.0.1:8554/xiaomi_cam", "online": True},
    {"id": "CAM-02", "name": "Линия сборки", "zone": "Цех № 1", "workshop": "Корпус А", "site_id": "north", "image_placeholder": "workshop", "online": True},
    {"id": "CAM-03", "name": "Участок станков", "zone": "Цех № 1", "workshop": "Корпус А", "site_id": "north", "image_placeholder": "workshop", "online": True},
    {"id": "CAM-04", "name": "Проход между станками", "zone": "Цех № 1", "workshop": "Корпус А", "site_id": "north", "image_placeholder": "workshop", "online": True},
    {"id": "CAM-05", "name": "Зона отдыха", "zone": "Цех № 1", "workshop": "Корпус А", "site_id": "north", "image_placeholder": "workshop", "online": True},
    {"id": "CAM-12", "name": "Межстеллажный проход", "zone": "Склад", "workshop": "Корпус Б", "site_id": "north", "image_placeholder": "warehouse", "online": True},
    {"id": "CAM-13", "name": "Зона комплектации", "zone": "Склад", "workshop": "Корпус Б", "site_id": "north", "image_placeholder": "warehouse", "online": True},
    {"id": "CAM-14", "name": "Стеллажи ЛКМ", "zone": "Склад", "workshop": "Корпус Б", "site_id": "north", "image_placeholder": "warehouse", "online": True},
    {"id": "CAM-16", "name": "Зона отгрузки", "zone": "Погрузочная зона", "workshop": "Корпус Б", "site_id": "north", "image_placeholder": "warehouse", "online": True},
    {"id": "CAM-17", "name": "Мостовой кран", "zone": "Погрузочная зона", "workshop": "Корпус Б", "site_id": "north", "image_placeholder": "workshop", "online": True},
    {"id": "CAM-08", "name": "Центральная проходная", "zone": "Проходная", "workshop": "Периметр", "site_id": "north", "image_placeholder": "gate", "online": True},
    {"id": "CAM-09", "name": "Пост охраны", "zone": "Проходная", "workshop": "Периметр", "site_id": "north", "image_placeholder": "gate", "online": True},
    {"id": "CAM-21", "name": "Северное ограждение", "zone": "Периметр", "workshop": "Периметр", "site_id": "north", "image_placeholder": "perimeter", "online": True},
    {"id": "CAM-19", "name": "Монтажная площадка", "zone": "Высотные работы", "workshop": "Периметр", "site_id": "north", "image_placeholder": "workshop", "online": False},
    {"id": "CAM-31", "name": "Зона разгрузки", "zone": "Зона разгрузки", "workshop": "Терминал", "site_id": "south", "image_placeholder": "warehouse", "online": True},
    {"id": "CAM-32", "name": "Парковка", "zone": "Парковка", "workshop": "КПП", "site_id": "south", "image_placeholder": "gate", "online": True},
    {"id": "CAM-33", "name": "Южные ворота", "zone": "Южные ворота", "workshop": "КПП", "site_id": "south", "image_placeholder": "gate", "online": True},
    {"id": "CAM-41", "name": "Котлован · север", "zone": "Котлован", "workshop": "Монтажный участок", "site_id": "east", "image_placeholder": "perimeter", "online": True},
    {"id": "CAM-42", "name": "Котлован · ограждение", "zone": "Котлован", "workshop": "Монтажный участок", "site_id": "east", "image_placeholder": "perimeter", "online": True},
    {"id": "CAM-43", "name": "Бытовой городок", "zone": "Бытовой городок", "workshop": "Склад стройматериалов", "site_id": "east", "image_placeholder": "workshop", "online": True},
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

        # 2. Проверяем наличие камер
        existing_cameras = db.scalar(select(Camera))
        if not existing_cameras:
            print("[Seed] Заполнение базы данных камерами...")
            for c_data in SEED_CAMERAS:
                camera = Camera(
                    id=c_data["id"],
                    name=c_data["name"],
                    zone=c_data["zone"],
                    workshop=c_data["workshop"],
                    site_id=c_data["site_id"],
                    image_placeholder=c_data["image_placeholder"],
                    rtsp_url=c_data.get("rtsp_url"),
                    online=c_data["online"],
                    last_heartbeat=datetime.utcnow()
                )
                db.add(camera)
            db.commit()
            print("[Seed] Камеры успешно созданы.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
