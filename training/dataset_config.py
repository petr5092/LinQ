"""Resolve dataset root exactly once for both validation and Ultralytics."""
from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

import yaml

@contextmanager
def normalized_data_yaml(source: Path):
    source = source.resolve(strict=True)
    config = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Dataset YAML must be a mapping")
    base = Path(config.get("path", "."))
    root = (source.parent / base).resolve() if not base.is_absolute() else base.resolve()
    config["path"] = root.as_posix()
    with tempfile.TemporaryDirectory(prefix="linq_yolo_config_") as temporary:
        target = Path(temporary) / "dataset.yaml"
        target.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
        yield target
