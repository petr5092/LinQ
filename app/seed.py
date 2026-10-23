"""
Модуль первичного наполнения базы данных справочными объектами, камерами и тестовыми инцидентами.
"""
from datetime import datetime
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models.site import Site, Workshop, Zone
from app.db.models.camera import Camera
from app.db.models.incident import Incident

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
    {"id": "CAM-01", "name": "Сборочный участок", "zone": "Цех № 1", "workshop": "Корпус А", "site_id": "north", "image_placeholder": "workshop", "online": True},
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

SEED_INCIDENTS = [
    {
        "id": "TK-1048",
        "site_id": "north",
        "camera_id": "CAM-01",
        "zone": "Цех № 1",
        "title": "Сотрудник без каски",
        "time": "14:32:08",
        "severity": "critical",
        "type": "person",
        "description": "Сотрудник находится в зоне работы оборудования без защитной каски более 15 секунд.",
        "action": "Свяжитесь с мастером смены. Остановите работы до устранения нарушения.",
        "image_key": "workshop",
        "status": "new",
        "box": [63, 43, 9, 32],
        "employee_name": "Иван Петров",
        "employee_role": "Оператор станка · Цех № 1",
        "employee_number": "00482",
        "employee_access": "Доступ разрешён · СКУД в 14:12",
        "contact_name": "Алексей Морозов",
        "contact_role": "Мастер смены",
        "contact_radio": "Канал 3 · Мастер-01",
        "contact_phone": "+7 (495) 555-01-20, доб. 203",
    },
    {
        "id": "TK-1047",
        "site_id": "north",
        "camera_id": "CAM-08",
        "zone": "Проходная",
        "title": "Попытка несанкционированного прохода",
        "time": "14:31:42",
        "severity": "critical",
        "type": "access",
        "description": "СКУД отклонила проход: срок допуска к работам истёк 22.10.2026. Турникет заблокирован.",
        "action": "Передайте информацию охране.",
        "image_key": "gate",
        "status": "new",
        "box": [48, 24, 13, 47],
        "employee_name": "Дмитрий Соколов",
        "employee_role": "Подрядчик · ООО «Монтаж»",
        "employee_number": "П-0136",
        "employee_access": "В проходе отказано · Допуск истёк",
        "contact_name": "Сергей Волков",
        "contact_role": "Начальник охраны",
        "contact_radio": "Канал 1 · Пост-01",
        "contact_phone": "+7 (495) 555-01-20, доб. 101",
    },
    {
        "id": "TK-1046",
        "site_id": "north",
        "camera_id": "CAM-12",
        "zone": "Склад",
        "title": "Ящик в проходе",
        "time": "14:30:16",
        "severity": "warning",
        "type": "environment",
        "description": "Посторонний ящик перекрывает пешеходный проход между стеллажами Б-3 и Б-4.",
        "action": "Свяжитесь с начальником склада и организуйте освобождение прохода.",
        "image_key": "warehouse",
        "status": "new",
        "box": [66, 43, 12, 17],
        "contact_name": "Елена Кузнецова",
        "contact_role": "Начальник склада",
        "contact_radio": "Канал 4 · Склад-01",
        "contact_phone": "+7 (495) 555-01-20, доб. 304",
    },
    {
        "id": "TK-1043",
        "site_id": "north",
        "camera_id": "CAM-16",
        "zone": "Погрузочная зона",
        "title": "Опасное сближение с погрузчиком",
        "time": "14:25:39",
        "severity": "critical",
        "type": "person",
        "description": "Расстояние от пешехода до движущегося погрузчика меньше 1,5 метра.",
        "action": "Предупредите водителя и остановите движение на участке.",
        "image_key": "warehouse",
        "status": "working",
        "box": [47, 36, 15, 39],
        "employee_name": "Андрей Смирнов",
        "employee_role": "Комплектовщик",
        "employee_number": "00317",
        "employee_access": "Доступ разрешён · СКУД в 13:58",
        "contact_name": "Елена Кузнецова",
        "contact_role": "Начальник склада",
        "contact_radio": "Канал 4 · Склад-01",
        "contact_phone": "+7 (495) 555-01-20, доб. 304",
    },
    {
        "id": "TK-1035",
        "site_id": "north",
        "camera_id": "CAM-05",
        "zone": "Цех № 1",
        "title": "Падение сотрудника",
        "time": "13:41:12",
        "severity": "critical",
        "type": "person",
        "description": "Зафиксировано падение и отсутствие движения в течение 20 секунд. Помощь оказана.",
        "action": "Проверьте акт оказания помощи и состояние участка.",
        "image_key": "workshop",
        "status": "resolved",
        "box": [37, 65, 28, 18],
        "contact_name": "Анна Белова",
        "contact_role": "Дежурный медработник",
        "contact_radio": "Канал 5 · Медпункт",
        "contact_phone": "+7 (495) 555-01-20, доб. 103",
    },
]


def seed_database():
    from app.db.base import Base
    from app.db.session import engine
    Base.metadata.create_all(bind=engine)
    """Заполнение БД базовыми объектами при пустой базе."""
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
                    online=c_data["online"],
                    last_heartbeat=datetime.utcnow()
                )
                db.add(camera)
            db.commit()
            print("[Seed] Камеры успешно созданы.")

        # 3. Проверяем наличие инцидентов
        existing_incidents = db.scalar(select(Incident))
        if not existing_incidents:
            print("[Seed] Заполнение тестовыми инцидентами...")
            for inc_data in SEED_INCIDENTS:
                incident = Incident(**inc_data)
                db.add(incident)
            db.commit()
            print("[Seed] Тестовые инциденты успешно созданы.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
