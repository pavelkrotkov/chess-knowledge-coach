"""Synthetic purpose diagnostic coverage."""

import chess
import chess.engine
import pytest

from tests.purpose_deadline_fixture import (
    assert_engine_deadlines,
    freeze_clock,
    install_recording_engine,
)


def test_remaining_deadline_bounds_search_and_skips_final(monkeypatch):
    from types import SimpleNamespace

    import chess_coach.purpose_deadline as deadline
    import chess_coach.purpose_search as search

    engine = SimpleNamespace(timeout=None)
    freeze_clock(monkeypatch, deadline)
    monkeypatch.setattr(search, "scout", lambda *_args: ({"lines": []}, "d2d4", None))
    monkeypatch.setattr(search, "final", lambda *_args: pytest.fail("final search started"))
    result, issue = search.search(engine, chess.Board(), {"uci": "e2e4"}, 11.0)
    assert issue == "worker_deadline" and "final" not in result
    assert engine.timeout == pytest.approx(0.4)
    assert deadline.startup_timeout(13.0) == pytest.approx(2.9 / 3)
    assert deadline.cleanup_timeout(9.0) == pytest.approx(0.001)


def test_engine_start_and_cleanup_use_remaining_deadline(monkeypatch):
    from types import SimpleNamespace

    import chess_coach.purpose_deadline as deadline
    import chess_coach.purpose_execute as execution

    engine = SimpleNamespace(timeout=None)
    config = {"engine_path": "/synthetic"}
    freeze_clock(monkeypatch, deadline)
    monkeypatch.setattr(execution, "configuration", lambda *_args: ("binary", config))
    calls = install_recording_engine(monkeypatch, execution, engine)
    monkeypatch.setattr(execution, "search", lambda *_args: ({}, None))
    snapshot = {"board": chess.Board(), "game_id": 1, "position": {"uci": "e2e4"}}
    status, detail, _result = execution.execute(None, snapshot, config, 13.0)
    assert (status, detail) == ("complete", "comparable")
    assert_engine_deadlines(calls)
