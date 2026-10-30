"""Durable server-directed backoff across bounded worker invocations."""

import sys
from datetime import UTC, datetime, timedelta

import chess
import chess.engine
import httpx
import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_status import pipeline_status


class Clock:
    def __init__(self):
        self.now = datetime.now(UTC).replace(microsecond=0)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class Engine:
    def __init__(self):
        self.id = {"name": "Fixture Engine"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        return [{"pv": [root_moves[0] if root_moves else next(iter(board.legal_moves))]}]

    def quit(self):
        pass


def add_game(db, number, at):
    pgn = f"""[Event "Synthetic {number}"]
[White "Learner"]
[Black "Opponent"]
[UTCDate "{at:%Y.%m.%d}"]
[UTCTime "{at:%H:%M:%S}"]
[Result "1-0"]

1. e4 e5 1-0
"""
    ingest_pgn(db, pgn)


def setup(tmp_path, monkeypatch):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner="learner",
        engine_path=sys.executable,
        nodes=10,
        seconds_per_position=0.1,
        network_retries=0,
        network_sleep=0,
    )
    return db, config, Clock()


def test_long_server_cooldown_survives_reopen_and_allows_local_progress(tmp_path, monkeypatch):
    db, config, clock = setup(tmp_path, monkeypatch)
    add_game(db, 1, clock())
    calls = []

    def limited(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "3600"})

    first = process_pipeline(db, config, transport=httpx.MockTransport(limited), clock=clock)
    expected = (clock() + timedelta(hours=1)).isoformat()
    assert first["sync"] == {
        "status": "waiting",
        "detail": "server_backoff",
        "retry_until": expected,
    }
    assert first["games"][0]["stages"][0]["status"] == "complete"
    assert len(calls) == 1
    path = db.path
    db.close()
    db = Database(path)
    clock.advance(1800)
    add_game(db, 2, clock())

    def success(request):
        calls.append(request)
        return httpx.Response(200, text="")

    second = process_pipeline(db, config, transport=httpx.MockTransport(success), clock=clock)
    assert second["sync"]["retry_until"] == expected and second["sync"]["status"] == "waiting"
    assert len(calls) == 1
    assert second["games"][0]["game_id"] == 2
    health = pipeline_status(db)["health"]
    assert health["retry_until"] == expected and health["sync_status"] == "waiting"
    clock.advance(1800)
    third = process_pipeline(db, config, transport=httpx.MockTransport(success), clock=clock)
    assert third["sync"]["status"] in {"complete", "partial"}
    assert len(calls) > 1
    assert pipeline_status(db)["health"]["retry_until"] is None


def test_interrupted_retry_wait_keeps_deadline_for_next_process(tmp_path, monkeypatch):
    db, config, clock = setup(tmp_path, monkeypatch)
    calls = []

    def limited(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "120"})

    def interrupt(seconds):
        assert seconds == 120
        raise KeyboardInterrupt()

    transport = httpx.MockTransport(limited)
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.pipeline_network_budget.time.sleep", interrupt)
        with pytest.raises(KeyboardInterrupt):
            process_pipeline(db, replace_config(config), transport=transport, clock=clock)
    expected = (clock() + timedelta(seconds=120)).isoformat()
    path = db.path
    db.close()
    db = Database(path)
    health = pipeline_status(db)["health"]
    assert health["retry_until"] == expected
    assert health["sync_status"] == "waiting" and health["sync_detail"] == "server_backoff"
    resumed = process_pipeline(db, config, transport=transport, clock=clock)
    assert resumed["sync"]["status"] == "waiting" and len(calls) == 1


def replace_config(config):
    from dataclasses import replace

    return replace(config, network_retries=1, network_sleep=120, network_seconds=180)


def test_due_retry_runs_during_analysis_and_survives_reopen(tmp_path, monkeypatch):
    import threading

    from chess_coach.pipeline_sync import sync_result
    from chess_coach.pipeline_work import run_analysis

    db, config, clock = setup(tmp_path, monkeypatch)
    add_game(db, 1, clock())
    started = threading.Event()
    release = threading.Event()
    errors = []

    class SlowEngine(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            started.set()
            assert release.wait(20)
            return super().analyse(board, limit, multipv, root_moves=root_moves)

    def analyze():
        worker_db = Database(db.path)
        try:
            result = run_analysis(worker_db, 1, "fixture", config, "fixture")
            assert result["status"] == "complete"
        except BaseException as exc:
            errors.append(exc)
        finally:
            worker_db.close()

    limited = httpx.MockTransport(lambda request: httpx.Response(429))
    first = process_pipeline(db, config, transport=limited, clock=clock)
    assert first["sync"]["status"] == "waiting"
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: SlowEngine())
    db.close()
    db = Database(tmp_path / "coach.sqlite")
    calls = []

    def success(request):
        calls.append(request)
        return httpx.Response(200, text="")

    transport = httpx.MockTransport(success)
    assert sync_result(db, config, None, transport, clock, retry_only=True) is None
    clock.advance(60)
    worker = threading.Thread(target=analyze)
    worker.start()
    try:
        assert started.wait(20)
        result = sync_result(db, config, None, transport, clock, retry_only=True)
        assert result["status"] in {"complete", "partial"}
        assert calls and worker.is_alive()
        assert pipeline_status(db)["health"]["retry_until"] is None
        assert sync_result(db, config, None, transport, clock, retry_only=True) is None
    finally:
        release.set()
        worker.join(20)
    assert not worker.is_alive() and not errors
