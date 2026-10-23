"""Шаблон адаптера LinQ TPU. Скопируйте в linq_adapter.py (рядом с run.py).

Здесь НЕТ реальных вызовов API: пример интеграции лежит в usage_example_python_api.zip
(ссылка в «Процедура_подготовки_и_инференса...pdf»), а сборка «Программы для TPU» из ONNX
описана в tpu_framework.pdf. Допишите три места, помеченных TODO.
"""
import numpy as np


def load(program_path):
    # TODO 1: подключиться к сервису инференса (VPN включён, логин/пароль Jupyter —
    #         у капитана) и загрузить скомпилированную Программу для TPU по program_path.
    # session = ...

    def run(tensor: np.ndarray) -> np.ndarray:
        # TODO 2: если Программа квантована, привести вход к нужному типу/масштабу
        #         (как в end-to-end примере из tpu_framework.pdf).
        # TODO 3: передать тензор через API, получить выходной тензор и вернуть его
        #         как float32 в той же раскладке, что у ONNX-модели: (1, 4+nc, N).
        raise NotImplementedError("допишите вызовы API LinQ")

    return run
