"""Record synthetic engine startup and cleanup limits."""

from types import SimpleNamespace

import pytest


def install_recording_engine(monkeypatch, execution, engine):
    calls = []

    def start(binary, runtime, *, timeout):
        calls.append(("start", timeout))
        return engine, SimpleNamespace(id={"name": "Synthetic"})

    def stop(stopped_engine):
        calls.append(("stop", stopped_engine.timeout))
        return True

    monkeypatch.setattr(execution, "start_engine", start)
    monkeypatch.setattr(execution, "stop_engine", stop)
    return calls


def freeze_clock(monkeypatch, deadline):
    monkeypatch.setattr(deadline, "time", SimpleNamespace(monotonic=lambda: 10.0))


def assert_engine_deadlines(calls):
    assert calls[0] == ("start", pytest.approx(2.9 / 3))
    assert calls[1] == ("stop", pytest.approx(3.0))
