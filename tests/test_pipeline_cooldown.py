"""Durable server-directed backoff across bounded worker invocations."""

import sys
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

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

    def analyse(self, board, limit, multipv):
        return [{"pv": [next(iter(board.legal_moves))]}]

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


def test_retry_after_http_date_and_missing_429_header(tmp_path, monkeypatch):
    db, config, clock = setup(tmp_path, monkeypatch)
    requested = clock() + timedelta(hours=2)
    result = process_pipeline(
        db,
        config,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                503, headers={"Retry-After": format_datetime(requested, usegmt=True)}
            )
        ),
        clock=clock,
    )
    assert result["sync"]["retry_until"] == requested.isoformat()
    clock.advance(7200)
    result = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(429)), clock=clock
    )
    assert result["sync"]["retry_until"] == (clock() + timedelta(seconds=60)).isoformat()


@pytest.mark.parametrize("status,content,bytes_limit", [(503, b"", 1024), (200, b"x" * 17, 16)])
def test_generic_failure_does_not_create_cooldown(
    tmp_path, monkeypatch, status, content, bytes_limit
):
    from dataclasses import replace

    db, config, clock = setup(tmp_path, monkeypatch)
    result = process_pipeline(
        db,
        replace(config, network_bytes=bytes_limit),
        transport=httpx.MockTransport(lambda request: httpx.Response(status, content=content)),
        clock=clock,
    )
    assert result["sync"]["detail"] in {"sync_failed", "network_budget_exhausted"}
    assert pipeline_status(db)["health"]["retry_until"] is None


def test_deadline_write_interrupted_by_alarm_is_retried_before_exit(tmp_path, monkeypatch):
    from chess_coach import pipeline_cooldown_storage
    from chess_coach.pipeline_network_response import BudgetExceeded

    db, config, clock = setup(tmp_path, monkeypatch)
    original = pipeline_cooldown_storage.persist_deadline
    attempts = []

    def interrupted(*args):
        attempts.append(1)
        if len(attempts) == 1:
            raise BudgetExceeded("synthetic deadline")
        return original(*args)

    monkeypatch.setattr("chess_coach.pipeline_cooldown_response.persist_deadline", interrupted)
    calls = []

    def limited(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "900"})

    result = process_pipeline(db, config, transport=httpx.MockTransport(limited), clock=clock)
    assert result["sync"]["status"] == "waiting" and len(attempts) == 2
    assert result["sync"]["retry_until"] == (clock() + timedelta(seconds=900)).isoformat()
    assert len(calls) == 1


def test_v14_upgrade_preserves_existing_health_and_adds_unknown_deadline(monkeypatch):
    from chess_coach import db_recent
    from chess_coach.pipeline_health import start_run

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_pipeline_cooldown", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=14")
    db.connection.commit()
    start_run(db)
    before = tuple(db.connection.execute("SELECT * FROM pipeline_health").fetchone())
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 15
    after = tuple(db.connection.execute("SELECT * FROM pipeline_health").fetchone())
    assert after[:-1] == before and after[-1] is None
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_v14_cooldown_migration_failure_is_atomic(monkeypatch):
    from chess_coach import db_recent
    from chess_coach.pipeline_cooldown_schema import add_pipeline_cooldown

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_pipeline_cooldown", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=14")
    db.connection.commit()

    def fail(connection):
        add_pipeline_cooldown(connection)
        raise RuntimeError("injected migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_pipeline_cooldown", fail)
        with pytest.raises(RuntimeError, match="injected migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 14
    assert "retry_until" not in {
        row[1] for row in db.connection.execute("PRAGMA table_info(pipeline_health)")
    }
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_later_shorter_server_deadline_never_shortens_existing_backoff(tmp_path, monkeypatch):
    from chess_coach.pipeline_cooldown_response import observe_response

    db, _, clock = setup(tmp_path, monkeypatch)
    observe_response(db, httpx.Response(503, headers={"Retry-After": "3600"}), clock)
    first = pipeline_status(db)["health"]["retry_until"]
    observe_response(db, httpx.Response(429, headers={"Retry-After": "60"}), clock)
    assert pipeline_status(db)["health"]["retry_until"] == first
    observe_response(db, httpx.Response(503, headers={"Retry-After": "7200"}), clock)
    assert (
        pipeline_status(db)["health"]["retry_until"] == (clock() + timedelta(hours=2)).isoformat()
    )


def test_naive_injected_clock_fails_before_any_request(tmp_path, monkeypatch):
    db, config, _ = setup(tmp_path, monkeypatch)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text="")

    with pytest.raises(ValueError, match="timezone-aware"):
        process_pipeline(
            db, config, transport=httpx.MockTransport(handler), clock=lambda: datetime(2026, 1, 1)
        )
    assert calls == []


@pytest.mark.parametrize("status", [429, 503])
def test_extreme_server_delay_never_becomes_short_retry(tmp_path, monkeypatch, status):
    db, config, clock = setup(tmp_path, monkeypatch)
    calls = []

    def limited(request):
        calls.append(request)
        return httpx.Response(status, headers={"Retry-After": "9" * 400})

    transport = httpx.MockTransport(limited)
    first = process_pipeline(db, config, transport=transport, clock=clock)
    assert first["sync"]["retry_until"] == datetime.max.replace(tzinfo=UTC).isoformat()
    assert (
        process_pipeline(db, config, transport=transport, clock=clock)["sync"]["status"]
        == "waiting"
    )
    assert len(calls) == 1


def test_response_body_budget_does_not_discard_received_retry_after(tmp_path, monkeypatch):
    from dataclasses import replace

    db, config, clock = setup(tmp_path, monkeypatch)
    calls = []

    def limited(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "300"}, content=b"xx")

    config = replace(config, network_bytes=1)
    transport = httpx.MockTransport(limited)
    first = process_pipeline(db, config, transport=transport, clock=clock)
    assert first["sync"]["retry_until"] == (clock() + timedelta(seconds=300)).isoformat()
    assert (
        process_pipeline(db, config, transport=transport, clock=clock)["sync"]["status"]
        == "waiting"
    )
    assert len(calls) == 1
