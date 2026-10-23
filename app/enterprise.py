"""Enterprise metadata used to attribute incidents to workshops and shifts."""
import json
import os
import re
from datetime import datetime, timedelta

from . import config

DEFAULT_SHIFTS = [
    {"name": "Смена 1", "start": "00:00", "end": "08:00"},
    {"name": "Смена 2", "start": "08:00", "end": "16:00"},
    {"name": "Смена 3", "start": "16:00", "end": "00:00"},
]
UNASSIGNED_WORKSHOP = "Не назначен"
UNASSIGNED_SHIFT = "Не определена"
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _minutes(value):
    match = _TIME.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError(f"неверное время смены {value!r}; используйте ЧЧ:ММ")
    return int(match.group(1)) * 60 + int(match.group(2))


class EnterpriseConfig:
    def __init__(self, path=None):
        self.path = path or os.path.join(config.ROOT, "configs", "enterprise.json")
        if os.path.isfile(self.path):
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"shifts": DEFAULT_SHIFTS, "camera_workshops": {}}
        if not isinstance(data, dict):
            raise ValueError("конфигурация предприятия должна быть JSON-объектом")

        shifts = data.get("shifts", DEFAULT_SHIFTS)
        workshops = data.get("camera_workshops", {})
        if not isinstance(shifts, list) or not shifts:
            raise ValueError("shifts должен содержать хотя бы одну смену")
        if not isinstance(workshops, dict):
            raise ValueError("camera_workshops должен быть JSON-объектом")

        self.shifts = []
        coverage = [0] * 1440
        for shift in shifts:
            if not isinstance(shift, dict) or not str(shift.get("name", "")).strip():
                raise ValueError("каждой смене требуется непустое имя")
            start, end = shift.get("start"), shift.get("end")
            start_min, end_min = _minutes(start), _minutes(end)
            if start_min == end_min:
                raise ValueError(f"смена {shift['name']!r} не может длиться 24 часа")
            if start_min < end_min:
                minutes = range(start_min, end_min)
            else:
                minutes = (*range(start_min, 1440), *range(0, end_min))
            for minute in minutes:
                coverage[minute] += 1
            self.shifts.append({"name": str(shift["name"]).strip(), "start": start, "end": end,
                                "_start": start_min, "_end": end_min})

        if any(n != 1 for n in coverage):
            raise ValueError("смены должны без пробелов и пересечений покрывать все сутки")
        self.camera_workshops = {}
        for camera, workshop in workshops.items():
            camera, workshop = str(camera).strip(), str(workshop).strip()
            if not camera or not workshop:
                raise ValueError("название камеры и участка не должны быть пустыми")
            self.camera_workshops[camera] = workshop

    def workshop_for(self, camera):
        return self.camera_workshops.get(camera, UNASSIGNED_WORKSHOP)

    def shift_for(self, timestamp):
        dt = datetime.fromtimestamp(timestamp)
        minute = dt.hour * 60 + dt.minute
        for shift in self.shifts:
            start, end = shift["_start"], shift["_end"]
            if start < end:
                matches = start <= minute < end
            else:
                matches = minute >= start or minute < end
            if matches:
                shift_date = dt.date()
                if start > end and minute < end:
                    shift_date -= timedelta(days=1)
                return shift["name"], shift_date.isoformat()
        raise RuntimeError("конфигурация смен не покрывает указанное время")
