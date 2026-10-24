"""Configuration shared by the standalone CV worker and benchmark."""
from pathlib import Path
import os
import yaml

from engine.rules.base import ViolationSeverity
from engine.rules.danger_zone import DangerZoneRule, ZoneDefinition
from engine.rules.engine import RulesEngine
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.rules.phone_usage import PhoneUsageRule
from engine.rules.proximity import ProximityRule

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
    cfg = config.get('rules', {})
    names = set(class_names.values())
    rules = RulesEngine()

    def enabled(key):
        return cfg.get(key, {}).get('enabled', False)

    def severity(key, default='HIGH'):
        return ViolationSeverity(cfg.get(key, {}).get('severity', default).upper())

    if enabled('danger_zone'):
        zones = []
        for row in camera.get('zones', []):
            missing = set(row.get('forbidden_classes', ['person'])) - names
            if missing:
                raise ValueError(f'Danger zone requires model classes: {sorted(missing)}')
            zones.append(ZoneDefinition(**{**row, 'severity': ViolationSeverity(row.get('severity', 'CRITICAL').upper())}))
        rules.add_rule(DangerZoneRule(zones=zones))
    if enabled('proximity'):
        row = cfg['proximity']
        vehicles = row.get('vehicle_classes', ['forklift', 'truck', 'machinery', 'car'])
        if 'person' not in names or not names.intersection(vehicles):
            raise ValueError('Proximity requires person and a configured vehicle class')
        rules.add_rule(ProximityRule(safe_distance_px=row.get('safe_distance_px', 140),
                                     vehicle_classes=vehicles, severity=severity('proximity')))
    if enabled('ppe_compliance'):
        row = cfg['ppe_compliance']
        required = {'person'}
        if row.get('require_helmet', True):
            required.add('helmet')
        if row.get('require_vest', True):
            required.add('vest')
        if required - names:
            raise ValueError(f'PPE rule requires model classes: {sorted(required - names)}. Disable unsupported rules.')
        rules.add_rule(PPEComplianceRule(require_helmet=row.get('require_helmet', True),
                                         require_vest=row.get('require_vest', True), severity=severity('ppe_compliance')))
    if enabled('fall_detection'):
        if 'person' not in names:
            raise ValueError('Fall rule requires person class')
        row = cfg['fall_detection']
        rules.add_rule(FallDetectionRule(aspect_ratio_thresh=row.get('aspect_ratio_threshold', 1.2),
                                         max_speed_px=row.get('max_speed_px', 2),
                                         min_frames_lying=row.get('min_frames_lying', 12),
                                         min_lying_seconds=row.get('min_lying_seconds', 3),
                                         severity=severity('fall_detection', 'CRITICAL')))
    if enabled('phone_usage'):
        if 'person' not in names or not names.intersection({'phone', 'cell phone', 'smartphone'}):
            raise ValueError('Phone rule requires person and phone/cell phone/smartphone classes')
        phone_class = next(name for name in ('phone', 'cell phone', 'smartphone') if name in names)
        rules.add_rule(PhoneUsageRule(phone_class_name=phone_class))
    return rules
