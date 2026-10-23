"""Все настройки в одном месте. Подгоняй под свою модель и объект."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("LINQ_DATA", os.path.join(ROOT, "data"))
SNAP_DIR = os.path.join(DATA_DIR, "snaps")

# Имена классов в порядке выходов вашей модели (YOLO). ОБЯЗАТЕЛЬНО сверьте с моделью.
CLASS_NAMES = ["person", "helmet", "no_helmet", "vest", "no_vest", "phone"]
INPUT_SIZE = 640
CONF_THR = 0.35
NMS_IOU = 0.5

# Параметры правил. Ключ — type правила (см. app/rules.py).
RULE_PARAMS = {
    "fall":            {"confirm_s": 2.0, "aspect": 1.25, "still_s": 1.0},
    "restricted_zone": {"confirm_s": 1.5},
    # mode: "negative" — модель умеет классы no_helmet/no_vest;
    #       "absence"  — нарушение, если каски/жилета в области головы/торса нет
    "no_helmet":       {"confirm_s": 2.0, "mode": "negative"},
    "no_vest":         {"confirm_s": 2.0, "mode": "negative"},
    "phone":           {"confirm_s": 2.0},
}

# Подавление повторов
ENGINE = {
    "gap_s": 2.0,        # пауза в нарушении, после которой оно считается новым
    "dedup_s": 20.0,     # окно защиты от смены ID трека (перекрытия)
    "dedup_dist": 0.06,  # доля ширины кадра
}
