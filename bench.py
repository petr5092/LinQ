"""Reproducible single-stream inference benchmark; not a multi-camera capacity test."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time

from dotenv import load_dotenv
from engine.config import ROOT, inference_options, load_config
from engine.inference.factory import create_inference_engine
from engine.sources.factory import create_video_source


def file_sha256(path):
    with open(path, 'rb') as stream:
        if hasattr(hashlib, 'file_digest'):
            return hashlib.file_digest(stream, 'sha256').hexdigest()
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(65536), b''):
            h.update(chunk)
        return h.hexdigest()


def percentile(data, p):
    if not data:
        raise ValueError('Cannot compute a percentile without measurements')
    values = sorted(data)
    position = (len(values) - 1) * p / 100
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def latency_summary(values):
    return {key: round(value, 3) for key, value in {
        'mean': statistics.mean(values), 'p50': percentile(values, 50),
        'p95': percentile(values, 95), 'min': min(values), 'max': max(values),
    }.items()}


def run_benchmark(engine, source, frames, warmup, source_spec):
    if frames <= 0 or warmup < 0:
        raise ValueError('frames must be positive and warmup nonnegative')
    totals, inference, preprocess, postprocess, with_decode = [], [], [], [], []
    iterator = iter(source)
    backend = None
    try:
        for index in range(frames + warmup):
            start = time.perf_counter()
            try:
                frame, _ = next(iterator)
            except StopIteration:
                break
            decoded = time.perf_counter()
            result = engine.infer(frame)
            done = time.perf_counter()
            if backend is not None and backend != result.metrics.backend_name:
                raise RuntimeError('Backend changed during benchmark')
            backend = result.metrics.backend_name
            if index >= warmup:
                totals.append((done - decoded) * 1000)
                with_decode.append((done - start) * 1000)
                inference.append(result.metrics.inference_time_ms)
                preprocess.append(result.metrics.preprocess_time_ms)
                postprocess.append(result.metrics.postprocess_time_ms)
    finally:
        source.stop()
        if hasattr(iterator, 'close'):
            iterator.close()
        engine.close()
    if not totals:
        raise ValueError('No measured frames: source must contain more frames than warmup')
    model_path = getattr(engine, 'model_path', None)
    checksum = None
    if model_path and Path(model_path).is_file():
        checksum = file_sha256(model_path)
    is_mock = backend == 'MOCK' or bool(getattr(engine, 'is_emulated', False))
    return {
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'backend': backend, 'is_emulated': is_mock,
        'model_path': model_path, 'model_sha256': checksum,
        'input_size_wh': list(engine.input_size), 'class_names': engine.class_names,
        'source': source_spec, 'synthetic_input': source_spec.startswith('synthetic'),
        'frames_requested': frames, 'frames_evaluated': len(totals), 'warmup_frames': warmup,
        'complete': len(totals) == frames,
        'inference_call_latency_ms': latency_summary(inference),
        'preprocess_mean_ms': statistics.mean(preprocess),
        'postprocess_mean_ms': statistics.mean(postprocess),
        'total_latency_ms': latency_summary(totals),
        'decode_and_inference_latency_ms': latency_summary(with_decode),
        'throughput_fps': 1000 / statistics.mean(totals),
        'decode_and_inference_fps': 1000 / statistics.mean(with_decode),
        'python': platform.python_version(), 'platform': platform.platform(),
        'note': ('MOCK: synthetic detections; no model or hardware evidence' if is_mock else
                 'ONNX Runtime CPU inference' if backend == 'ONNX_CPU' else
                 'LinQ adapter call including transfers and synchronization; verify physical hardware on the stand'),
        'scope': 'Single stream. Excludes tracking, rules, storage, network delivery and GUI latency. Does not prove multi-camera capacity.',
    }


def main(argv=None):
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--backend', default='mock', choices=['mock', 'onnx', 'linq', 'onnx_cpu', 'linq_tpu'])
    parser.add_argument('--model')
    parser.add_argument('--source', default='synthetic')
    parser.add_argument('--frames', type=int, default=200)
    parser.add_argument('--warmup', type=int, default=10)
    parser.add_argument('--out', default='bench_results.json')
    args = parser.parse_args(argv)
    if args.frames <= 0 or args.warmup < 0:
        parser.error('--frames must be positive and --warmup nonnegative')
    config = load_config(args.config)
    engine = create_inference_engine(**inference_options(config, args.backend, args.model))
    try:
        source = create_video_source(args.source, realtime=False, loop=False)
    except Exception:
        engine.close()
        raise
    summary = run_benchmark(engine, source, args.frames, args.warmup, args.source)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
