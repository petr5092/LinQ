"""Configuration shared by the standalone CV worker and benchmark."""
from pathlib import Path
import os
import yaml

from engine.rules.registry import build_configured_rules_engine

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    config_path = Path(path) if path else ROOT / 'configs' / 'cv_engine.yaml'
    with config_path.open(encoding='utf-8') as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError('CV configuration must be a YAML mapping')
    return config


def inference_options(config, backend=None, model=None):
    cfg = config.get('inference', {})
    backend = (backend or os.getenv('INFERENCE_BACKEND') or cfg.get('backend', 'ONNX_CPU')).upper()
    aliases = {'ONNX': 'ONNX_CPU', 'LINQ': 'LINQ_TPU'}
    backend = aliases.get(backend, backend)
    path_key = 'tpu_model_path' if backend == 'LINQ_TPU' else 'onnx_model_path'
    env_key = 'TPU_MODEL_PATH' if backend == 'LINQ_TPU' else 'ONNX_MODEL_PATH'
    path = model or os.getenv(env_key) or cfg.get(path_key)
    if path and not Path(path).is_absolute():
        path = str(ROOT / path)
    names = cfg.get('class_names')
    if isinstance(names, list):
        names = dict(enumerate(names))
    elif names is not None:
        names = {int(key): value for key, value in names.items()}
    options = dict(backend=backend, model_path=path,
                   conf_threshold=float(os.getenv('CONFIDENCE_THRESHOLD', cfg.get('confidence_threshold', 0.35))),
                   iou_threshold=float(os.getenv('IOU_THRESHOLD', cfg.get('iou_threshold', 0.45))),
                   input_size=tuple(cfg.get('input_size', [640, 640])), class_names=names)
    if backend == 'LINQ_TPU' and cfg.get('adapter_module'):
        options['adapter_module'] = cfg['adapter_module']
    return options


def build_rules(config, camera, class_names):
    return build_configured_rules_engine(config, camera, class_names)
