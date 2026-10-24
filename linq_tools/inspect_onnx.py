"""Validate the CV model contract and print exact class and tensor names."""
import argparse
import hashlib
import json
from pathlib import Path
from engine.inference.local_onnx import LocalONNXEngine


def inspect_model(path):
    with LocalONNXEngine(str(path)) as engine:
        with open(path, 'rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        return {'model': str(Path(path).resolve()), 'sha256': checksum,
                'input_name': engine.input_name, 'output_names': engine.output_names,
                'input_shape': [1, 3, engine.input_size[1], engine.input_size[0]],
                'class_names': engine.class_names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model')
    parser.add_argument('--out')
    args = parser.parse_args()
    text = json.dumps(inspect_model(args.model), ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
