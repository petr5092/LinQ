"""Replay an open CSV temperature matrix into the thermal ingestion API."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_temperature_matrix(path: Path) -> list[list[float]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = [[float(value) for value in row] for row in csv.reader(source) if row]
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("CSV must contain a non-empty rectangular matrix")
    if len(rows) > 512 or len(rows[0]) > 640:
        raise ValueError("CSV matrix exceeds the API limit of 640x512 pixels")
    if not all(math.isfinite(value) for row in rows for value in row):
        raise ValueError("CSV matrix contains a non-finite temperature")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="CSV with one Celsius value per pixel")
    parser.add_argument("--camera-id", default="THERMAL-OSF-TEST")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--repeats", type=int, default=1, help="Repeat one static frame (for debounce smoke checks)")
    parser.add_argument("--interval", type=float, default=1.0, help="Delay in seconds between repeats")
    args = parser.parse_args()
    if args.repeats < 1 or args.interval < 0:
        parser.error("--repeats must be positive and --interval must be non-negative")
    matrix = load_temperature_matrix(args.csv_file)
    height, width = len(matrix), len(matrix[0])
    url = f"{args.api_url.rstrip('/')}/thermal/cameras/{args.camera_id}/frame"

    import time

    for index in range(args.repeats):
        payload = json.dumps({
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "temperatures": matrix,
        }).encode("utf-8")
        request = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"Thermal API returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise SystemExit(f"Cannot reach thermal API at {url}: {exc.reason}") from exc
        print(f"Frame {index + 1}/{args.repeats}: {width}x{height}")
        for measurement in result.get("measurements", []):
            print(
                f"  {measurement['zone_name']}: max={measurement['max_temperature_c']:.2f}°C "
                f"threshold={measurement['threshold_c']:.2f}°C alarm={measurement['alarm']}"
            )
        if index + 1 < args.repeats:
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
