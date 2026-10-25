"""Analyze numeric radiometric frames without depending on a camera vendor SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class ThermalZone:
    zone_id: str
    name: str
    roi: tuple[float, float, float, float]
    max_temperature_c: float
    clear_temperature_c: float
    min_hot_pixels: int = 1
    min_frames: int = 3
    severity: str = "critical"
    action: str = "Проверьте оборудование и устраните причину перегрева."

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ThermalZone":
        roi = value.get("roi")
        if not isinstance(roi, (list, tuple)) or len(roi) != 4:
            raise ValueError("Thermal zone roi must be [x1, y1, x2, y2] in normalized coordinates")
        coords = tuple(float(v) for v in roi)
        if not all(math.isfinite(v) for v in coords) or not (0 <= coords[0] < coords[2] <= 1 and 0 <= coords[1] < coords[3] <= 1):
            raise ValueError("Thermal zone roi coordinates must satisfy 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1")
        maximum = float(value["max_temperature_c"])
        clear = float(value.get("clear_temperature_c", maximum - 5.0))
        if not math.isfinite(maximum) or not math.isfinite(clear) or clear >= maximum:
            raise ValueError("clear_temperature_c must be finite and lower than max_temperature_c")
        min_hot_pixels = int(value.get("min_hot_pixels", 1))
        min_frames = int(value.get("min_frames", 3))
        if min_hot_pixels < 1 or min_frames < 1:
            raise ValueError("min_hot_pixels and min_frames must be positive")
        severity = str(value.get("severity", "critical")).lower()
        if severity not in {"critical", "warning", "info"}:
            raise ValueError("Thermal severity must be critical, warning or info")
        return cls(
            zone_id=str(value["zone_id"]),
            name=str(value.get("name", value["zone_id"])),
            roi=coords,
            max_temperature_c=maximum,
            clear_temperature_c=clear,
            min_hot_pixels=min_hot_pixels,
            min_frames=min_frames,
            severity=severity,
            action=str(value.get("action", "Проверьте оборудование и устраните причину перегрева.")),
        )


@dataclass
class ThermalMeasurement:
    zone_id: str
    zone_name: str
    roi: tuple[float, float, float, float]
    min_temperature_c: float
    mean_temperature_c: float
    max_temperature_c: float
    hot_pixels: int
    threshold_c: float
    alarm: bool
    alarm_started: bool = False
    action: str = ""
    severity: str = "warning"

    def as_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "roi": list(self.roi),
            "min_temperature_c": self.min_temperature_c,
            "mean_temperature_c": self.mean_temperature_c,
            "max_temperature_c": self.max_temperature_c,
            "hot_pixels": self.hot_pixels,
            "threshold_c": self.threshold_c,
            "alarm": self.alarm,
            "alarm_started": self.alarm_started,
            "action": self.action,
            "severity": self.severity,
        }


@dataclass
class _ZoneState:
    consecutive_hot_frames: int = 0
    alarm_active: bool = False


class ThermalAnalyzer:
    """Apply configurable ROI temperature thresholds with debounce and hysteresis."""

    def __init__(self, zones: Sequence[ThermalZone | Mapping[str, Any]]) -> None:
        self.zones = tuple(zone if isinstance(zone, ThermalZone) else ThermalZone.from_mapping(zone) for zone in zones)
        if not self.zones:
            raise ValueError("At least one thermal zone must be configured")
        if len({zone.zone_id for zone in self.zones}) != len(self.zones):
            raise ValueError("Thermal zone_id values must be unique")
        self._states = {zone.zone_id: _ZoneState() for zone in self.zones}

    @staticmethod
    def validate_frame(temperatures: Any) -> np.ndarray:
        try:
            frame = np.asarray(temperatures, dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise ValueError("temperatures must be a rectangular 2D numeric matrix in Celsius") from exc
        if frame.ndim != 2 or not frame.size or frame.shape[0] > 512 or frame.shape[1] > 640:
            raise ValueError("temperature matrix must be 2D and no larger than 640x512 pixels")
        if not np.isfinite(frame).all():
            raise ValueError("temperature matrix must contain only finite values")
        if float(frame.min()) < -273.15 or float(frame.max()) > 3000:
            raise ValueError("temperature values must be between -273.15°C and 3000°C")
        return frame

    def process(self, temperatures: Any) -> list[ThermalMeasurement]:
        frame = self.validate_frame(temperatures)
        height, width = frame.shape
        measurements: list[ThermalMeasurement] = []
        for zone in self.zones:
            x1 = min(width - 1, int(zone.roi[0] * width))
            y1 = min(height - 1, int(zone.roi[1] * height))
            x2 = max(x1 + 1, min(width, int(math.ceil(zone.roi[2] * width))))
            y2 = max(y1 + 1, min(height, int(math.ceil(zone.roi[3] * height))))
            values = frame[y1:y2, x1:x2]
            max_c = float(values.max())
            hot_pixels = int(np.count_nonzero(values >= zone.max_temperature_c))
            state = self._states[zone.zone_id]
            alarm_started = False
            if hot_pixels >= zone.min_hot_pixels:
                state.consecutive_hot_frames += 1
                if not state.alarm_active and state.consecutive_hot_frames >= zone.min_frames:
                    state.alarm_active = True
                    alarm_started = True
            else:
                state.consecutive_hot_frames = 0
                if state.alarm_active and max_c <= zone.clear_temperature_c:
                    state.alarm_active = False
            # Announce once per alarm episode, even if the hot condition persists.
            measurements.append(ThermalMeasurement(
                zone_id=zone.zone_id,
                zone_name=zone.name,
                roi=zone.roi,
                min_temperature_c=round(float(values.min()), 2),
                mean_temperature_c=round(float(values.mean()), 2),
                max_temperature_c=round(max_c, 2),
                hot_pixels=hot_pixels,
                threshold_c=zone.max_temperature_c,
                alarm=state.alarm_active,
                alarm_started=alarm_started,
                action=zone.action if state.alarm_active else "",
                severity=zone.severity,
            ))
        return measurements

    def reset(self) -> None:
        for state in self._states.values():
            state.consecutive_hot_frames = 0
            state.alarm_active = False
