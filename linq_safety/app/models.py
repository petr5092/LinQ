"""Общие структуры данных."""
from dataclasses import dataclass, field


@dataclass
class Detection:
    cls: str
    conf: float
    box: tuple  # x1, y1, x2, y2 в пикселях кадра


@dataclass
class Frame:
    img: object            # numpy RGB, HxWx3 uint8
    t: float               # время потока, сек (монотонно растёт)
    wall: float            # perf_counter() в момент захвата — для замера задержки
    meta: dict = field(default_factory=dict)
