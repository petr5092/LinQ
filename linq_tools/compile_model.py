"""Prepare a non-raw H1M TPU program using the SDK 2026.9.45 documented API.

Run inside the organizer's Linux SDK environment. This tool has not been run on
the absent safety model; successful compilation and TPU/ONNX parity are required.
Source: tpu_framework.pdf, chapter 5, PDF pages 31-36.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np

from engine.inference.local_onnx import LocalONNXEngine


def calibration_batch(directory, samples, preprocess):
    paths = sorted(path for path in Path(directory).iterdir() if path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'})
    tensors = []
    selected = []
    for path in paths:
        image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f'Cannot decode calibration image: {path}')
        tensors.append(preprocess(image)[0])
        selected.append(str(path))
        if len(tensors) >= samples:
            break
    if not tensors:
        raise ValueError('Calibration directory has no images')
    return np.concatenate(tensors, axis=0), selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--onnx', required=True)
    parser.add_argument('--calibration', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--samples', type=int, default=50)
    args = parser.parse_args(argv)
    if args.samples < 1:
        parser.error('--samples must be positive')
    # SDK dependencies are supplied by LinQ, not installed as guessed PyPI packages.
    import onnx
    from tpu_framework import RegularModel, Network, TPU_H1M, O1, TpuProgram, compiler
    with LocalONNXEngine(args.onnx) as engine:
        tensors, paths = calibration_batch(args.calibration, args.samples, engine.preprocess)
        input_name = engine.input_name
        output_names = engine.output_names
        classes = engine.class_names
        input_shape = [1, 3, engine.input_size[1], engine.input_size[0]]
    regular = RegularModel(model=onnx.load(args.onnx))
    thresholds = regular.calibrate({regular.anchors_mapping[input_name]: tensors})
    quantized = regular.quantize(thresholds)
    network, renaming = Network.from_quantized_model(quantized)
    network.set_batch(1)
    executable, descriptions = compiler.compile_(TPU_H1M, network, O1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    TpuProgram.from_executable(executable, descriptions).to_file(str(out))
    def sha256(path):
        with open(path, 'rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = {'compiled_at_utc': datetime.now(timezone.utc).isoformat(), 'profile': 'TPU_H1M', 'optimization': 'O1',
                'onnx_sha256': sha256(args.onnx), 'tpu_sha256': sha256(out),
                'input_name': input_name, 'output_names': output_names, 'input_shape': input_shape,
                'class_names': classes, 'calibration_images': paths,
                'preprocessing': 'engine.inference.yolo.letterbox: RGB float32 NCHW /255, padding=114',
                'hardware_verified': False}
    out.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Compiled {out}. Validate outputs against ONNX on physical TPU before claiming hardware readiness.')


if __name__ == '__main__':
    main()
