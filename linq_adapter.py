"""Native pytpu adapter following LinQ's usage_example_python_api.zip.

Source: https://cloud.lin-q.ru/s/QcFLdkdLb71BOmm
The native SDK and a physical device are required. For a remote service with a
different API, use its supplied notebook and a separate LINQ_ADAPTER_MODULE.
"""
from contextlib import ExitStack
import os
import numpy as np


class NativeRuntime:
    def __init__(self, program_path):
        try:
            import pytpu as tpu
        except ImportError as exc:
            raise RuntimeError('Install pytpu from the organizer SDK on the LinQ host; this is not a PyPI dependency') from exc
        self._stack = ExitStack()
        self._closed = False
        self.input_name = os.getenv('LINQ_INPUT_NAME', 'images')
        self.output_name = os.getenv('LINQ_OUTPUT_NAME', 'output0')
        try:
            devices = tpu.Device.list_devices()
            index = int(os.getenv('LINQ_DEVICE_INDEX', '0'))
            if index < 0 or index >= len(devices):
                raise RuntimeError('No LinQ TPU at the configured device index; inspect /dev/tpu* on the stand')
            device = self._stack.enter_context(tpu.Device.open(devices[index]))
            program = self._stack.enter_context(device.load(str(program_path)))
            self._inference = self._stack.enter_context(program.inference())
            # SDK 2026.9.45 documents sync(); the separate older Python example
            # uses run(). Both are documented interfaces, not guessed methods.
            self._run = getattr(self._inference, 'sync', None)
            if not callable(self._run):
                self._run = getattr(self._inference, 'run', None)
            if not callable(self._run):
                raise RuntimeError('Installed pytpu exposes neither documented sync() nor run() API')
        except Exception:
            self._stack.close()
            raise

    def __call__(self, tensor):
        if self._closed:
            raise RuntimeError('LinQ runtime is closed')
        if tensor.dtype != np.float32 or tensor.ndim != 4 or tensor.shape[:2] != (1, 3):
            raise ValueError('Expected float32 [1, 3, H, W] input')
        outputs = self._run({self.input_name: np.ascontiguousarray(tensor)})
        if self.output_name not in outputs:
            raise ValueError(f'Configured output {self.output_name!r} absent; set LINQ_OUTPUT_NAME from compiled graph')
        return outputs[self.output_name]

    def close(self):
        if not self._closed:
            self._closed = True
            self._stack.close()


def load(program_path):
    return NativeRuntime(program_path)
