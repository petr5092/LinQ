"""Contract for an optional custom/remote LinQ adapter.

The default native implementation already exists in linq_adapter.py and follows
the official Python example and SDK 2026.9.45. Do not overwrite it with this
template. Use this file under a different module name only if the organizer's
remote service uses a different API, then set LINQ_ADAPTER_MODULE accordingly.

Set INFERENCE_BACKEND=LINQ_TPU, TPU_MODEL_PATH=<compiled program>,
LINQ_ADAPTER_MODULE=<your custom module> and supply the original model's class names and
static input size. Do not install an unrelated package named pytpu from PyPI.

load(program_path) must open the physical accelerator, load the compiled program,
validate its input/output shapes and return a callable runtime object:

* runtime(tensor) accepts contiguous float32 RGB NCHW [1, 3, H, W], values [0, 1].
* Convert/quantize inputs exactly as configured during compilation.
* Wait for device completion and output transfer before returning (timed by HAL).
* Dequantize outputs to float32; return raw YOLO [1, 4+C, N] or [1, N, 4+C].
  A dict must use the configured output node name (default output0).
* runtime.close() should release resources. Release partially opened resources
  inside load() when initialization fails. Propagate hardware errors.

Confirm outputs against ONNX on the same frames before recording TPU performance.
The HAL's inference time includes the adapter call and transfers; it is not an
isolated chip latency measurement.
"""


def load(program_path):
    raise NotImplementedError(
        "Implement the LinQ adapter from the organizer's official Python API example "
        "for the installed SDK and compiled model; hardware inference is not configured."
    )
