"""
Замер производительности инференса нейросети на LinQ TPU и ONNX Runtime:
    python bench.py --backend onnx --model models/onnx/best.onnx --frames 200
    python bench.py --backend linq --model models/tpu/best.tpu --frames 300
    python bench.py --backend mock --frames 100

Результат выводится в консоль и сохраняется в bench_results.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics as st
import time

from engine.inference.factory import create_inference_engine
from engine.sources.synthetic import SyntheticSource


def percentile(data: list[float], p: float) -> float:
    """Расчет p-го процентиля."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = min(len(sorted_data) - 1, int(len(sorted_data) * p / 100.0))
    return sorted_data[idx]


def main():
    parser = argparse.ArgumentParser(description="Бенчмарк инференса LinQ TPU / ONNX Runtime")
    parser.add_argument("--backend", default="mock", choices=["mock", "onnx", "linq", "onnx_cpu", "linq_tpu", "linq_remote"],
                        help="Бэкенд вычислений (linq = LinQ TPU H1M, onnx = ONNX Runtime CPU, mock = эмуляция)")
    parser.add_argument("--model", default=None, help="Путь к файлу скомпилированной модели (.tpu или .onnx)")
    parser.add_argument("--frames", type=int, default=200, help="Количество кадров для тестового прогона")
    parser.add_argument("--warmup", type=int, default=10, help="Количество кадров прогрева")
    parser.add_argument("--target-fps", type=float, default=10.0, help="Целевая частота кадров на одну камеру")
    parser.add_argument("--out", default="bench_results.json", help="Путь к результирующему JSON-файлу")
    parser.add_argument("--endpoint", default=None, help="URL удаленного LinQ TPU сервиса (например http://10.0.114.5:8080)")
    args = parser.parse_args()

    # Нормализуем имя бэкенда для фабрики
    backend_map = {
        "linq": "linq_tpu",
        "linq_tpu": "linq_tpu",
        "linq_remote": "linq_remote",
        "onnx": "onnx_cpu",
        "onnx_cpu": "onnx_cpu",
        "mock": "mock",
    }
    backend_name = backend_map.get(args.backend.lower(), "mock")

    print(f"=== Инициализация движка {backend_name} (модель: {args.model}) ===")
    engine = create_inference_engine(
        backend=backend_name,
        model_path=args.model,
        remote_url=args.endpoint,
    )

    print(f"Генерация синтетических тестовых кадров (прогрев: {args.warmup}, замер: {args.frames})...")
    source = SyntheticSource(fps=30.0, realtime=False, max_frames=args.frames + args.warmup)

    total_times_ms: list[float] = []
    infer_times_ms: list[float] = []
    pre_times_ms: list[float] = []
    post_times_ms: list[float] = []

    for i, (frame, _) in enumerate(source):
        t0 = time.perf_counter()
        result = engine.infer(frame)
        t_total = (time.perf_counter() - t0) * 1000.0

        if i >= args.warmup:
            total_times_ms.append(t_total)
            infer_times_ms.append(result.metrics.inference_time_ms)
            pre_times_ms.append(result.metrics.preprocess_time_ms)
            post_times_ms.append(result.metrics.postprocess_time_ms)

    mean_total = st.mean(total_times_ms) if total_times_ms else 1e-3
    throughput_fps = 1000.0 / max(mean_total, 1e-3)

    summary = {
        "backend": getattr(engine, "name", getattr(engine, "backend_name", engine.__class__.__name__)),
        "is_emulated": getattr(engine, "is_emulated", False),
        "model_path": args.model,
        "frames_evaluated": len(total_times_ms),
        "total_latency_ms": {
            "mean": round(mean_total, 2),
            "p50": round(percentile(total_times_ms, 50), 2),
            "p95": round(percentile(total_times_ms, 95), 2),
            "min": round(min(total_times_ms), 2) if total_times_ms else 0.0,
            "max": round(max(total_times_ms), 2) if total_times_ms else 0.0,
        },
        "stages_mean_ms": {
            "preprocess": round(st.mean(pre_times_ms), 2) if pre_times_ms else 0.0,
            "inference": round(st.mean(infer_times_ms), 2) if infer_times_ms else 0.0,
            "postprocess": round(st.mean(post_times_ms), 2) if post_times_ms else 0.0,
        },
        "throughput_fps": round(throughput_fps, 1),
        "target_fps_per_camera": args.target_fps,
        "max_concurrent_cameras": int(throughput_fps // args.target_fps) if args.target_fps > 0 else 0,
        "note": "Режим эмуляции (без физического TPU)" if getattr(engine, "is_emulated", False) or backend_name == "mock" else "Аппаратный замер на LinQ TPU",
    }

    print("\n=== Результаты замера производительности ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nОтчет сохранен в файл: {args.out}")


if __name__ == "__main__":
    main()
