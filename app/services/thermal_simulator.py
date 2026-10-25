import asyncio
import csv
import logging
import math
from pathlib import Path
import time
from typing import Optional

import numpy as np

from app.config import BASE_DIR

logger = logging.getLogger("linq.thermal_simulator")


class ThermalCameraSimulator:
    """Simulate a realistic radiometric thermal camera stream with dynamic overheating cycles."""

    def __init__(
        self,
        camera_id: str = "THERMAL-OSF-TEST",
        cycle_seconds: float = 120.0,
        fps: float = 1.0,
        sample_csv: Optional[Path] = None,
    ) -> None:
        self.camera_id = camera_id
        self.cycle_seconds = max(30.0, cycle_seconds)
        self.fps = max(0.2, min(10.0, fps))
        self.start_time = time.monotonic()
        self._base_pattern = self._load_or_create_base(sample_csv)

    def _load_or_create_base(self, sample_csv: Optional[Path]) -> np.ndarray:
        csv_path = sample_csv or (BASE_DIR / "data" / "thermal" / "osf_sample" / "Beef_LR_38_20_30.csv")
        if csv_path.is_file():
            try:
                with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                    rows = [[float(v) for v in row] for row in csv.reader(f) if row]
                arr = np.asarray(rows, dtype=np.float32)
                if arr.ndim == 2 and arr.size > 0:
                    c_min, c_max = float(arr.min()), float(arr.max())
                    if c_max > c_min:
                        # Normalized to [0.0, 1.0]
                        return (arr - c_min) / (c_max - c_min)
            except Exception as e:
                logger.warning(f"Could not load thermal sample from {csv_path}: {e}")

        # Fallback synthetic 80x60 matrix with mild gradient
        height, width = 80, 60
        y, x = np.ogrid[:height, :width]
        dist = np.sqrt(((x - width / 2) / (width / 2)) ** 2 + ((y - height / 2) / (height / 2)) ** 2)
        pattern = np.clip(1.0 - dist * 0.5, 0.0, 1.0).astype(np.float32)
        return pattern

    def generate_frame(self) -> np.ndarray:
        now = time.monotonic()
        elapsed = (now - self.start_time) % self.cycle_seconds
        h, w = self._base_pattern.shape

        # Normal base temperature range: 18.5 C to 20.3 C (safe below threshold 21.0 C)
        frame = 18.5 + self._base_pattern * 1.8

        # Thermal cycle phases:
        # Phase 1: 0 to 75s (~1.25 min) -> Safe normal operation
        # Phase 2: 75 to 100s (25s) -> Overheating anomaly (reaches ~23.8 C, crosses 21 C)
        # Phase 3: 100 to 120s (20s) -> Active cooling down below 20.0 C
        hotspot_intensity = 0.0
        if 75.0 <= elapsed < 100.0:
            # Overheating pulse
            progress = (elapsed - 75.0) / 25.0
            hotspot_intensity = float(math.sin(progress * math.pi) * 3.8)
        elif 100.0 <= elapsed < 112.0:
            # Residual heat cooling down
            progress = (elapsed - 100.0) / 12.0
            hotspot_intensity = float(math.exp(-progress * 3.0) * 0.8)

        if hotspot_intensity > 0.0:
            cy, cx = h // 2, w // 2
            y, x = np.ogrid[:h, :w]
            sigma_y, sigma_x = h * 0.18, w * 0.22
            gaussian = np.exp(-(((y - cy) / sigma_y) ** 2 + ((x - cx) / sigma_x) ** 2) / 2.0)
            frame = frame + gaussian.astype(np.float32) * hotspot_intensity

        # Add realistic micro-sensor noise (+/- 0.04 C)
        noise = np.random.normal(0.0, 0.04, size=(h, w)).astype(np.float32)
        frame = frame + noise
        return np.round(frame, 2)


async def run_thermal_simulator(
    stop_event: asyncio.Event,
    camera_id: str = "THERMAL-OSF-TEST",
    cycle_seconds: float = 120.0,
    fps: float = 1.0,
) -> None:
    """Background async worker simulating live radiometric frames for a thermal camera."""
    from app.db.session import SessionLocal
    from app.db.models.camera import Camera
    from app.routes.thermal import is_external_ingest_active, process_thermal_matrix

    logger.info(f"[{camera_id}] Запуск виртуального симулятора тепловизора (цикл {cycle_seconds:.0f}с, {fps:.1f} FPS)...")
    sim = ThermalCameraSimulator(camera_id=camera_id, cycle_seconds=cycle_seconds, fps=fps)
    interval = 1.0 / sim.fps

    while not stop_event.is_set():
        try:
            if is_external_ingest_active(camera_id):
                # An external client (or test replay) is currently sending frames; yield
                await asyncio.sleep(interval)
                continue

            frame = sim.generate_frame()
            with SessionLocal() as db:
                camera = db.get(Camera, camera_id)
                if camera and camera.camera_type == "thermal":
                    await process_thermal_matrix(
                        db=db,
                        camera_id=camera_id,
                        temperatures=frame,
                        captured_at=None,
                        is_external=False,
                    )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"[{camera_id}] Ошибка в цикле симулятора тепловизора: {e}")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass

    logger.info(f"[{camera_id}] Виртуальный симулятор тепловизора остановлен.")
