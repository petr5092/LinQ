from contextlib import contextmanager
import sys
from types import SimpleNamespace
import numpy as np
import pytest
from linq_adapter import load


def sdk(monkeypatch, fail=False):
    events = []
    @contextmanager
    def session():
        events.append('session.open')
        try:
            def run(inputs):
                assert list(inputs) == ['images']
                return {'output0': np.zeros((1, 5, 2), np.float32)}
            yield SimpleNamespace(run=run)
        finally:
            events.append('session.close')
    @contextmanager
    def program(path):
        events.append('program.open')
        if fail:
            raise RuntimeError('bad program')
        try:
            yield SimpleNamespace(inference=session)
        finally:
            events.append('program.close')
    @contextmanager
    def device(path):
        events.append('device.open')
        try:
            yield SimpleNamespace(load=program)
        finally:
            events.append('device.close')
    monkeypatch.setitem(sys.modules, 'pytpu', SimpleNamespace(Device=SimpleNamespace(list_devices=lambda: ['/dev/tpu0'], open=device)))
    for name in ('LINQ_INPUT_NAME', 'LINQ_OUTPUT_NAME', 'LINQ_DEVICE_INDEX'):
        monkeypatch.delenv(name, raising=False)
    return events


def test_official_api_lifecycle_and_run(monkeypatch):
    events = sdk(monkeypatch)
    runtime = load('model.tpu')
    assert runtime(np.zeros((1, 3, 2, 2), np.float32)).shape == (1, 5, 2)
    runtime.close()
    runtime.close()
    assert events == ['device.open', 'program.open', 'session.open', 'session.close', 'program.close', 'device.close']
    with pytest.raises(RuntimeError, match='closed'):
        runtime(np.zeros((1, 3, 2, 2), np.float32))


def test_partial_load_failure_releases_device(monkeypatch):
    events = sdk(monkeypatch, fail=True)
    with pytest.raises(RuntimeError, match='bad program'):
        load('model.tpu')
    assert events == ['device.open', 'program.open', 'device.close']


def test_no_device_is_an_error(monkeypatch):
    monkeypatch.setitem(sys.modules, 'pytpu', SimpleNamespace(Device=SimpleNamespace(list_devices=lambda: [])))
    with pytest.raises(RuntimeError, match='No LinQ TPU'):
        load('model.tpu')


def test_sdk_2026_sync_method_is_preferred(monkeypatch):
    sdk(monkeypatch)
    from contextlib import nullcontext
    calls = []
    session = SimpleNamespace(sync=lambda inputs: calls.append('sync') or {'output0': np.zeros((1, 5, 2), np.float32)},
                              run=lambda inputs: (_ for _ in ()).throw(AssertionError('run must not be used')))
    program = SimpleNamespace(inference=lambda: nullcontext(session))
    device = SimpleNamespace(load=lambda path: nullcontext(program))
    monkeypatch.setitem(sys.modules, 'pytpu', SimpleNamespace(Device=SimpleNamespace(list_devices=lambda: ['tpu0'], open=lambda path: nullcontext(device))))
    runtime = load('model.tpu')
    runtime(np.zeros((1, 3, 2, 2), np.float32))
    runtime.close()
    assert calls == ['sync']
