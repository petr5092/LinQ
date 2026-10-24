import json
import numpy as np
import pytest
from engine.inference.mock import MockInferenceEngine
from engine.inference.base import InferenceResult, InferenceMetrics
from engine.sources.synthetic import SyntheticSource
from bench import main, run_benchmark, percentile


def test_benchmark_excludes_warmup_and_marks_mock():
    engine = MockInferenceEngine(simulated_delay_ms=0)
    source = SyntheticSource(realtime=False, max_frames=5)
    result = run_benchmark(engine, source, 3, 2, 'synthetic')
    assert result['frames_evaluated'] == 3
    assert result['backend'] == 'MOCK_ENGINE' and result['is_emulated']
    assert result['complete']
    assert result['model_sha256'] is None
    assert 'max_concurrent_cameras' not in result
    assert not engine.is_loaded and source.is_stopped()


def test_short_source_is_disclosed():
    result = run_benchmark(MockInferenceEngine(), SyntheticSource(realtime=False, max_frames=2), 3, 1, 'clip.mp4')
    assert result['frames_evaluated'] == 1
    assert result['complete'] is False
    assert result['synthetic_input'] is False


def test_zero_measurements_cannot_report_fps():
    with pytest.raises(ValueError, match='No measured frames'):
        run_benchmark(MockInferenceEngine(), SyntheticSource(realtime=False, max_frames=1), 3, 1, 'synthetic')


def test_cpu_is_not_labelled_tpu(tmp_path):
    class CPU:
        model_path = str(tmp_path / 'model.onnx')
        input_size = (640, 640)
        class_names = {0: 'person'}
        def infer(self, frame):
            return InferenceResult(metrics=InferenceMetrics(inference_time_ms=1, backend_name='ONNX_CPU'))
        def close(self):
            pass
    (tmp_path / 'model.onnx').write_bytes(b'fixture')
    result = run_benchmark(CPU(), SyntheticSource(realtime=False, max_frames=1), 1, 0, 'synthetic')
    assert result['note'] == 'ONNX Runtime CPU inference'
    assert result['is_emulated'] is False and len(result['model_sha256']) == 64


@pytest.mark.parametrize('args', [['--frames', '0'], ['--warmup', '-1']])
def test_invalid_benchmark_arguments(args):
    with pytest.raises(SystemExit) as err:
        main(args)
    assert err.value.code == 2


def test_percentile_interpolation():
    assert percentile([1, 3], 50) == 2

