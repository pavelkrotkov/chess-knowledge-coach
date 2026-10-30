"""Synthetic scheduling, budget and source-scope checks."""

import json
import sys
import time

import chess
import chess.engine

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.style_schedule_budget import history_budget
from chess_coach.style_schedule_store import create_cycle
from tests.test_deep_selection import LEARNER, OPPONENT

CHECK = """[Event "Synthetic check"]
[UTCDate "2026.02.01"]
[UTCTime "00:00:00"]
[White "fixture_learner"]
[Black "fixture_opponent"]
[Result "*"]

1. e4 e5 2. Bc4 Nf6 3. Nf3 Bc5 4. Nxe5 Bxf2+ 5. Kxf2 *
"""

CONTROL = """[Event "Synthetic control"]
[UTCDate "2026.01.01"]
[UTCTime "00:00:00"]
[White "fixture_opponent"]
[Black "fixture_learner"]
[Result "*"]

1. d4 d5 2. c4 e6 3. Nc3 Nf6 *
"""


def test_recent_target_and_control_are_distinct_and_durable(tmp_path):
    db = Database(tmp_path / "schedule.sqlite")
    db.initialize()
    assert ingest_pgn(db, CHECK)["games"] == 1
    assert ingest_pgn(db, CONTROL)["games"] == 1
    with history_budget() as budget:
        cycle = create_cycle(db, LEARNER)
    rows = db.connection.execute(
        "SELECT kind,game_id,position_id,status FROM style_schedule_slots WHERE cycle_id=? ORDER BY id",
        (cycle,),
    ).fetchall()
    assert [row["kind"] for row in rows] == ["target", "control"]
    assert rows[0]["game_id"] != rows[1]["game_id"]
    assert rows[0]["status"] == "ready"
    assert rows[1]["status"] == "ready"
    assert 0 < budget["used"] <= 500
    coverage = json.loads(
        db.connection.execute(
            "SELECT coverage_json FROM style_schedule_cycles WHERE id=?", (cycle,)
        ).fetchone()[0]
    )
    assert coverage["examined_games"] == 2
    assert coverage["without_completed_analysis_checkpoint"] == 2
    assert coverage["reconstructed_games"] == 2
    assert coverage["scan_history_unit_limit"] == 500
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0


def test_empty_recent_sample_is_explicit_unknown():
    db = Database(":memory:")
    db.initialize()
    with history_budget():
        cycle = create_cycle(db, OPPONENT)
    rows = db.connection.execute(
        "SELECT status,detail FROM style_schedule_slots WHERE cycle_id=?", (cycle,)
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("unknown", "target_not_found_in_scanned_sample"),
        ("unknown", "control_not_found_in_scanned_sample"),
    ]


class SyntheticEngine:
    def __init__(self):
        self.id = {"name": "Synthetic"}
        self.options = {}

    def configure(self, _settings):
        pass

    def analyse(self, board, _limit, multipv, root_moves=None):
        roots = root_moves if root_moves is not None else list(board.legal_moves)[:multipv]
        lines = []
        for index, move in enumerate(roots):
            replay = board.copy()
            pv = [move]
            replay.push(move)
            for _ in range(3):
                next_move = next(iter(replay.legal_moves))
                pv.append(next_move)
                replay.push(next_move)
            lines.append(
                {
                    "pv": pv,
                    "score": chess.engine.PovScore(chess.engine.Cp(index * 10), board.turn),
                    "depth": 5,
                    "nodes": 100,
                    "time": 0.1,
                }
            )
        return lines

    def quit(self):
        pass


def test_worker_schedules_and_completes_two_owned_purpose_slots(tmp_path, monkeypatch):
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.style_schedule_status import status
    from chess_coach.style_schedule_worker import process_schedule

    db = Database(tmp_path / "worker.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: SyntheticEngine()
    )
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable)
    result = process_schedule(db, config, deadline=time.monotonic() + 20)
    assert result["history_used"] <= 2000
    assert len(result["processed"]) == 2
    assert [item["status"] for item in result["processed"]] == ["complete", "complete"]
    view = status(db, LEARNER)
    assert [slot["source_state"] for slot in view["slots"]] == ["current", "current"]
    assert view["pending"] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0


def test_cycles_rotate_controls_without_rewriting_prior_allocations(tmp_path):
    db = Database(tmp_path / "rotation.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    with history_budget():
        first = create_cycle(db, LEARNER)
    original = [
        tuple(row)
        for row in db.connection.execute(
            "SELECT kind,game_id,position_id,status FROM style_schedule_slots WHERE cycle_id=? ORDER BY id",
            (first,),
        )
    ]
    with history_budget():
        second = create_cycle(db, LEARNER)
    later = [
        tuple(row)
        for row in db.connection.execute(
            "SELECT kind,game_id,position_id,status FROM style_schedule_slots WHERE cycle_id=? ORDER BY id",
            (second,),
        )
    ]
    assert original[0][1] == later[0][1]
    assert original[1][2] != later[1][2]
    assert original == [
        tuple(row)
        for row in db.connection.execute(
            "SELECT kind,game_id,position_id,status FROM style_schedule_slots WHERE cycle_id=? ORDER BY id",
            (first,),
        )
    ]


def test_abandoned_claim_is_recorded_and_retry_preserves_history(tmp_path, monkeypatch):
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.purpose_claim import claim
    from chess_coach.purpose_request import create
    from chess_coach.style_schedule_store import update_slot
    from chess_coach.style_schedule_worker import process_schedule

    db = Database(tmp_path / "recovery.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    with history_budget():
        cycle = create_cycle(db, LEARNER)
    slot = db.connection.execute(
        "SELECT * FROM style_schedule_slots WHERE cycle_id=? AND kind='target'", (cycle,)
    ).fetchone()
    request_id = create(db, slot["position_id"], LEARNER, engine_path=sys.executable)["request_id"]
    update_slot(db, slot["id"], "running", "worker_claimed", request_id)
    claimed, _ = claim(db, request_id, LEARNER, retry=False)
    assert claimed is not None
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: SyntheticEngine()
    )
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable)
    process_schedule(db, config, deadline=time.monotonic() + 20)
    assert (
        db.connection.execute(
            "SELECT status FROM purpose_analysis_attempts WHERE request_id=?", (request_id,)
        ).fetchone()[0]
        == "interrupted"
    )
    process_schedule(db, config, deadline=time.monotonic() + 20)
    assert [
        row[0]
        for row in db.connection.execute(
            "SELECT status FROM purpose_analysis_attempts WHERE request_id=? ORDER BY attempt_number",
            (request_id,),
        )
    ] == ["interrupted", "complete"]


def test_family_arbitration_alternates_and_caps_each_deadline(monkeypatch):
    import chess_coach.pipeline_deep_arbitration as arbitration

    order = []
    sequence = [0]
    monkeypatch.setattr(arbitration, "next_sequence", lambda *_: ("key", sequence[0]))
    monkeypatch.setattr(arbitration.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(
        arbitration,
        "process_deep",
        lambda _db, _config, deadline: order.append(("normal", deadline)) or {},
    )
    monkeypatch.setattr(
        arbitration,
        "process_schedule",
        lambda _db, _config, deadline: order.append(("purpose", deadline)) or {},
    )
    config = type("Config", (), {"deep_enabled": True, "learner": "synthetic"})()
    arbitration.process_deep_cycle(None, config)
    assert order == [("normal", 125.0), ("purpose", 125.0)]
    order.clear()
    sequence[0] = 1
    arbitration.process_deep_cycle(None, config)
    assert order == [("purpose", 125.0), ("normal", 125.0)]


def test_budget_stops_malformed_excess_history_without_partial_observation(tmp_path, monkeypatch):
    import chess_coach.style_schedule_budget as limits

    db = Database(tmp_path / "budget.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    monkeypatch.setattr(limits, "LIMIT", 4)
    with history_budget() as budget:
        cycle = create_cycle(db, LEARNER)
    assert budget["used"] == 4
    row = db.connection.execute(
        "SELECT coverage_json FROM style_schedule_cycles WHERE id=?", (cycle,)
    ).fetchone()
    assert json.loads(row[0])["history_budget_exhausted"] is True
    assert all(
        row[0] == "unknown"
        for row in db.connection.execute(
            "SELECT status FROM style_schedule_slots WHERE cycle_id=?", (cycle,)
        )
    )


def test_schema30_upgrade_rollback_and_legacy_rows_survive(monkeypatch):
    import pytest

    from chess_coach import db_recent
    from tests.purpose_db_snapshot import schema_objects, typed_rows

    original = db_recent.add_style_schedule
    monkeypatch.setattr(db_recent, "add_style_schedule", lambda _connection: None)
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, CHECK)
    db.connection.execute("PRAGMA user_version=29")
    db.connection.commit()
    before_objects = schema_objects(db)
    tables = [row[1] for row in before_objects if row[0] == "table"]
    before_rows = typed_rows(db, tables)

    def fail_after_schema(connection):
        original(connection)
        raise RuntimeError("synthetic migration failure")

    monkeypatch.setattr(db_recent, "add_style_schedule", fail_after_schema)
    with pytest.raises(RuntimeError, match="synthetic migration failure"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 29
    assert schema_objects(db) == before_objects
    assert typed_rows(db, tables) == before_rows
    monkeypatch.setattr(db_recent, "add_style_schedule", original)
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 31
    assert schema_objects(db) >= before_objects
    assert typed_rows(db, tables) == before_rows
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()


def test_cli_and_private_get_show_current_and_stale_without_search_or_writes(
    tmp_path, monkeypatch, capsys
):
    from chess_coach.cli import main
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.style_schedule_worker import process_schedule
    from tests.purpose_browser_fixtures import app, browser_get

    path = tmp_path / "status.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: SyntheticEngine()
    )
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable)
    process_schedule(db, config, deadline=time.monotonic() + 20)
    before = [
        tuple(row)
        for row in db.connection.execute(
            "SELECT id,status,detail,request_id FROM style_schedule_slots ORDER BY id"
        )
    ]
    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("GET started engine")),
    )
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "style-choices", "--learner", LEARNER]
    )
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["purpose_schedule"]["state"] == "current"
    assert report["coverage"]["effective_game_limit"] == 100
    assert all(slot["source_state"] == "current" for slot in report["purpose_schedule"]["slots"])
    page = browser_get(app(path).test_client(), "/style-choices")
    assert page.status_code == 200
    assert b"Recent purpose comparisons" in page.data
    assert b"effective maximum 10" in page.data
    assert b"not a random or representative sample" in page.data
    assert before == [
        tuple(row)
        for row in db.connection.execute(
            "SELECT id,status,detail,request_id FROM style_schedule_slots ORDER BY id"
        )
    ]
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    db.connection.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
    db.connection.commit()
    from chess_coach.style_schedule_status import status

    assert status(db, LEARNER)["slots"][0]["status"] == "stale"


def test_crash_between_enqueue_and_slot_link_reuses_same_request(tmp_path, monkeypatch):
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.purpose_request import create
    from chess_coach.style_schedule_worker import process_schedule

    db = Database(tmp_path / "enqueue.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    with history_budget():
        cycle = create_cycle(db, LEARNER)
    slot = db.connection.execute(
        "SELECT * FROM style_schedule_slots WHERE cycle_id=? AND kind='target'", (cycle,)
    ).fetchone()
    request_id = create(db, slot["position_id"], LEARNER, engine_path=sys.executable)["request_id"]
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: SyntheticEngine()
    )
    process_schedule(
        db,
        PipelineConfig(learner=LEARNER, engine_path=sys.executable),
        deadline=time.monotonic() + 20,
    )
    assert (
        db.connection.execute(
            "SELECT request_id FROM style_schedule_slots WHERE id=?", (slot["id"],)
        ).fetchone()[0]
        == request_id
    )
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM purpose_analysis_requests WHERE position_id=?",
            (slot["position_id"],),
        ).fetchone()[0]
        == 1
    )


def test_existing_pipeline_lock_excludes_concurrent_scheduler(tmp_path):
    import pytest

    from chess_coach.pipeline import process_pipeline
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_lock import pipeline_lock

    db = Database(tmp_path / "locked.sqlite")
    db.initialize()
    with pipeline_lock(db.path), pytest.raises(RuntimeError, match="already running"):
        process_pipeline(db, PipelineConfig(learner=LEARNER, engine_path=sys.executable))
    assert db.connection.execute("SELECT COUNT(*) FROM style_schedule_cycles").fetchone()[0] == 0


def test_normal_deep_deadline_prevents_search(monkeypatch):
    from types import SimpleNamespace

    import chess_coach.purpose_deadline as clock
    from chess_coach.deep_execution_search import _bounded

    monkeypatch.setattr(clock.time, "monotonic", lambda: 10.0)
    engine = SimpleNamespace(timeout=None)
    called = []

    def operation(*_args):
        called.append(True)

    result, reason = _bounded(engine, 10.5, SimpleNamespace(time=1.0), operation)
    assert result == [] and reason == "worker_deadline"
    assert called == []


def test_oversized_game_is_unknown_but_other_games_still_rotate(tmp_path, monkeypatch):
    import chess_coach.style_schedule_budget as budget_module

    db = Database(tmp_path / "long-game.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    monkeypatch.setattr(budget_module, "GAME_LIMIT", 6)
    with history_budget():
        cycle = create_cycle(db, LEARNER)
    coverage = json.loads(
        db.connection.execute(
            "SELECT coverage_json FROM style_schedule_cycles WHERE id=?", (cycle,)
        ).fetchone()[0]
    )
    assert coverage["skipped_games"] == 1
    assert coverage["reconstructed_games"] == 1
    assert coverage["history_budget_exhausted"] is False
    rows = db.connection.execute(
        "SELECT kind,status,detail FROM style_schedule_slots WHERE cycle_id=? ORDER BY id", (cycle,)
    ).fetchall()
    assert tuple(rows[0]) == ("target", "unknown", "target_not_found_in_scanned_sample")
    assert rows[1]["status"] == "ready"


def test_missing_or_foreign_schedule_schema_fails_closed():
    import pytest

    from chess_coach.style_schedule_status import status

    db = Database(":memory:")
    db.initialize()
    db.connection.execute("DROP INDEX idx_style_schedule_owner")
    with pytest.raises(RuntimeError, match="foreign or incomplete"):
        status(db, LEARNER)


def test_source_change_during_worker_is_recorded_as_stale(tmp_path, monkeypatch):
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.style_schedule_worker import process_schedule

    db = Database(tmp_path / "source-change.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)

    class ChangingEngine(SyntheticEngine):
        def analyse(self, board, _limit, multipv, root_moves=None):
            result = super().analyse(board, _limit, multipv, root_moves)
            if root_moves is not None:
                db.connection.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
                db.connection.commit()
            return result

    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: ChangingEngine()
    )
    result = process_schedule(
        db,
        PipelineConfig(learner=LEARNER, engine_path=sys.executable),
        deadline=time.monotonic() + 20,
    )
    assert result["processed"][0]["status"] == "stale"
    assert (
        db.connection.execute(
            "SELECT status FROM style_schedule_slots WHERE cycle_id=? AND kind='target'",
            (result["cycle_id"],),
        ).fetchone()[0]
        == "stale"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0


def test_history_reconstruction_stops_at_shared_deadline(monkeypatch):
    import pytest

    import chess_coach.style_schedule_clock as clock
    from chess_coach.style_schedule_budget import BudgetExceeded, consume

    monkeypatch.setattr(clock.time, "monotonic", lambda: 10.0)
    with history_budget(deadline=10.0), pytest.raises(BudgetExceeded, match="worker deadline"):
        consume()


def test_arbitration_failure_does_not_starve_other_family(monkeypatch):
    import chess_coach.pipeline_deep_arbitration as arbitration

    calls = []
    monkeypatch.setattr(arbitration, "next_sequence", lambda *_: ("key", 1))

    def broken(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    def normal(*_args, **_kwargs):
        calls.append("normal")
        return {"status": "complete"}

    monkeypatch.setattr(arbitration, "process_schedule", broken)
    monkeypatch.setattr(arbitration, "process_deep", normal)
    config = type("Config", (), {"deep_enabled": True, "learner": "synthetic"})()
    deep, purpose = arbitration.process_deep_cycle(None, config)
    assert deep["status"] == "complete"
    assert purpose == {"status": "partial", "detail": "purpose_schedule_unavailable"}
    assert calls == ["normal"]
