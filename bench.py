"""Замер скорости детектора: python bench.py --backend onnx --model best.onnx --frames 200
Результат печатается и сохраняется в bench_results.json — вставьте в презентацию.
Для честных цифр на LinQ запускайте на ВМ с ускорителем (--backend linq)."""
import argparse
import json
import statistics as st
import time

from app import config, sources
from app.detector import make_detector
from app.models import Frame


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p / 100))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="onnx", choices=["mock", "onnx", "linq"])
    ap.add_argument("--model")
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--target-fps", type=float, default=10.0, help="сколько кадров/с на камеру нужно")
    ap.add_argument("--out", default="bench_results.json")
    a = ap.parse_args()
    det = make_detector(a.backend, a.model)
    src = sources.SyntheticSource(realtime=False, max_frames=a.frames + a.warmup)
    tot, inf, pre, post = [], [], [], []
    for i, f in enumerate(src):
        t0 = time.perf_counter()
        det.detect(f)
        dt = (time.perf_counter() - t0) * 1e3
        if i >= a.warmup:
            tot.append(dt); inf.append(det.last["infer_ms"]); pre.append(det.last["pre_ms"]); post.append(det.last["post_ms"])
    fps = 1000 / max(st.mean(tot), 1e-3)
    res = {"backend": det.name, "frames": len(tot),
           "total_ms": {"mean": round(st.mean(tot), 2), "p50": round(pct(tot, 50), 2), "p95": round(pct(tot, 95), 2)},
           "stages_ms_mean": {"pre": round(st.mean(pre), 2), "infer": round(st.mean(inf), 2), "post": round(st.mean(post), 2)},
           "throughput_fps": round(fps, 1), "target_fps_per_camera": a.target_fps,
           "max_cameras_at_target": int(fps // a.target_fps),
           "note": "mock-детектор не выполняет инференс: цифры не отражают модель" if a.backend == "mock" else ""}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
