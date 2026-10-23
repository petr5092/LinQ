"""
Компиляция и квантование нейросети детекции СИЗ (YOLOv8n) под ускоритель LinQ TPU (чип H1M).
Реализует полный цикл сборки .tpu программы согласно спецификации LinQ SDK (tpu_framework):
1. Оптимизация и предварительное кондиционирование графа ONNX;
2. Калибровка порогов квантования (FP19 / INT8);
3. Квантование и генерация графа;
4. Компиляция под архитектуру TPU_H1M с пресетами оптимизации O1 / O5.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Tuple
import numpy as np

try:
    import onnx
    from tpu_framework import (
        O1,
        O5,
        TPU_H1M,
        Network,
        QuantizedModel,
        RegularModel,
        TpuProgram,
        compiler,
        preliminary_model_conditioning,
    )
    HAS_TPU_FRAMEWORK = True
except ImportError:
    HAS_TPU_FRAMEWORK = False
    onnx = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Компилятор ONNX-модели в формат LinQ TPU (.tpu)")
    parser.add_argument(
        "--model",
        type=str,
        default="models/onnx/safety_yolov8n.onnx",
        help="Путь к входному ONNX файлу со статическими размерностями [1, 3, 640, 640]",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/tpu",
        help="Директория для сохранения скомпилированной .tpu программы",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="O1",
        choices=["O1", "O5"],
        help="Уровень оптимизации компилятора LinQ TPU (O1 или O5)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="h1m",
        help="Целевая аппаратная платформа (h1m)",
    )
    return parser.parse_args()


def get_initializer_names(onnx_model_proto: onnx.ModelProto) -> Tuple[str, ...]:
    return tuple(i.name for i in onnx_model_proto.graph.initializer)


def remove_initialized_inputs(onnx_model_proto: onnx.ModelProto) -> None:
    """Удаляет входы из секции inputs, если они присутствуют в initializers."""
    name_to_input = {i.name: i for i in onnx_model_proto.graph.input}
    initializer_names = get_initializer_names(onnx_model_proto)
    for initializer_name in initializer_names:
        if initializer_name in name_to_input:
            onnx_model_proto.graph.input.remove(name_to_input[initializer_name])


def compile_for_linq_tpu(model_path: str, output_dir: str, preset_name: str = "O1", platform: str = "h1m") -> str:
    if not HAS_TPU_FRAMEWORK:
        print("\n[ВНИМАНИЕ] Пакет `tpu_framework` не найден в текущем локальном окружении.")
        print("Библиотеки LinQ TPU скомпилированы под Linux x86_64.")
        print(f"Для компиляции на сервере/ВМ выполните:")
        print(f"  python linq_tools/compile_safety_model.py --model {model_path} --preset {preset_name}")
        return ""

    model_path = os.path.abspath(model_path)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Файл модели {model_path} не найден.")

    os.makedirs(output_dir, exist_ok=True)
    network_name = os.path.splitext(os.path.basename(model_path))[0]
    preset = O5 if preset_name.upper() == "O5" else O1

    opt_model_path = os.path.join(output_dir, f"{network_name}_opt.onnx")
    thresholds_path = os.path.join(output_dir, f"thresholds_{network_name}.json")
    quant_model_path = os.path.join(output_dir, f"quant_{network_name}.qm.onnx")
    quant_graph_path = os.path.join(output_dir, f"quant_{network_name}.pt2")
    program_name = f"{network_name}_b1_{preset_name.lower()}_{platform}.tpu"
    program_path = os.path.join(output_dir, program_name)

    print(f"\n=== Этап 1/3: Оптимизация и подготовка ONNX графа ===")
    onnx_model = onnx.load(model_path)
    remove_initialized_inputs(onnx_model)

    input_nodes = {i.name: [d.dim_value for d in i.type.tensor_type.shape.dim] for i in onnx_model.graph.input}
    for name, shape in input_nodes.items():
        if 0 in shape:
            raise ValueError(f"Динамическая размерность недопустима для LinQ TPU: {name} -> {shape}")

    onnx_model_optimized = preliminary_model_conditioning(onnx_model)
    onnx.save(onnx_model_optimized, opt_model_path)
    print(f"Оптимизированный ONNX сохранен: {opt_model_path}")

    print(f"\n=== Этап 2/3: Квантование и калибровка порогов ===")
    onnx_model_opt = onnx.load(opt_model_path)
    input_nodes_opt = {i.name: [d.dim_value for d in i.type.tensor_type.shape.dim] for i in onnx_model_opt.graph.input}
    input_shapes = list(input_nodes_opt.values())
    batch = input_shapes[0][0]

    # Генерация калибровочного тензора в допустимом диапазоне [0, 1]
    calibration_dict = {name: np.random.uniform(0.0, 1.0, size=shape).astype(np.float32) for name, shape in input_nodes_opt.items()}

    regular_model = RegularModel(model=onnx_model_opt)
    thresholds = regular_model.calibrate_torch(calibration_data=calibration_dict)
    RegularModel.dump_thresholds(thresholds_path, thresholds)
    print(f"Пороги квантования сохранены в: {thresholds_path}")

    quant_model = regular_model.quantize(thresholds)
    quant_model.save(file_dir=output_dir, file_name=f"quant_{network_name}.qm.onnx")

    quant_torch_graph = quant_model.as_torch_graph(batch_size=batch)
    quant_torch_graph.export_to_pt2(quant_graph_path)
    print(f"Квантованная модель сохранена: {quant_model_path}")

    print(f"\n=== Этап 3/3: Компиляция под ускоритель LinQ TPU ({platform}) ===")
    quantized_model = QuantizedModel.load(quant_model_path)
    network, _ = Network.from_quantized_model(quantized_model)

    tlm_program = compiler.compile_(
        hardware_parameters=TPU_H1M,
        network=network,
        parameters=preset,
    )

    executable, tensor_descriptions = tlm_program
    tpu_program = TpuProgram.from_executable(executable, tensor_descriptions)
    tpu_program.to_file(program_path)

    print(f"\nКомпиляция успешно завершена! Итоговая программа LinQ TPU:")
    print(f"-> {program_path} ({os.path.getsize(program_path) / (1024*1024):.2f} MB)")
    return program_path


if __name__ == "__main__":
    args = parse_args()
    compile_for_linq_tpu(
        model_path=args.model,
        output_dir=args.output_dir,
        preset_name=args.preset,
        platform=args.platform,
    )
