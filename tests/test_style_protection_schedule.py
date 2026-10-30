"""Synthetic source-bound protection scheduling."""

import json
import sys
import time

import chess.engine
import pytest

from chess_coach.pipeline_config import PipelineConfig
from chess_coach.style_schedule_worker import process_schedule
from tests.test_style_protection_source import fixture
from tests.test_style_schedule import SyntheticEngine


def force_control(monkeypatch, position_id, overlap):
    import chess_coach.style_schedule_candidates as candidates

    original = candidates.choose

    def choose(db, key, kind, choices):
        if kind == "target":
            return None
        if kind == "control":
            return (
                next((item for item in choices if item["position_id"] == position_id), None)
                if overlap
                else None
            )
        return original(db, key, kind, choices)

    monkeypatch.setattr(candidates, "choose", choose)


@pytest.mark.parametrize(("black", "overlap"), [(False, False), (True, False), (False, True)])
def test_current_owned_protection_allocates_and_preserves_original_source(
    tmp_path, monkeypatch, black, overlap
):
    from chess_coach.style_schedule_status import status

    db, learner, position_id, evidence = fixture(
        tmp_path / "protection.sqlite", monkeypatch, black=black
    )
    force_control(monkeypatch, position_id, overlap)
    before = [tuple(row) for row in db.connection.execute("SELECT * FROM evidence_mappings")]
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda *_a, **_k: SyntheticEngine())
    result = process_schedule(
        db,
        PipelineConfig(learner=learner, engine_path=sys.executable),
        deadline=time.monotonic() + 25,
    )
    row = db.connection.execute(
        "SELECT * FROM style_protection_allocations WHERE cycle_id=?", (result["cycle_id"],)
    ).fetchone()
    assert row["position_id"] == position_id
    assert row["evidence_id"] == evidence
    assert row["status"] in ("complete", "insufficient")
    assert row["request_id"] is not None
    binding = json.loads(row["binding_json"])
    assert binding["provenance"]["objective_target"] == ("c6" if black else "c3")
    assert binding["provenance"]["review_status"] == "unreviewed"
    assert result["history_used"] <= 2000
    assert result["protection_resolutions"]["used"] <= 3
    assert result["native_work"]["job_limit"] == 3
    assert result["native_work"]["search_limit"] == 6
    assert result["native_work"]["requested_node_limit"] == 750000
    assert result["native_work"]["searches_observed"] == 2
    assert result["native_work"]["actual_nodes_observed_lower_bound"] == 200
    assert result["native_work"]["work_unknown"] is False
    assert [
        tuple(row) for row in db.connection.execute("SELECT * FROM evidence_mappings")
    ] == before
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    if overlap:
        assert row["slot_id"] is not None
        assert any(item["allocations"] == ["control", "protection"] for item in result["processed"])
        assert len(result["processed"]) == 1
        slot = db.connection.execute(
            "SELECT request_id FROM style_schedule_slots WHERE id=?", (row["slot_id"],)
        ).fetchone()
        assert slot["request_id"] == row["request_id"]
    else:
        assert row["slot_id"] is None
        assert result["processed"][0]["slot"] == "protection"
    view = status(db, learner)
    assert view["protection"]["source_state"] == "current"
    assert view["protection"]["review_status"] == "unreviewed"
    assert view["protection"]["target"] == ("c6" if black else "c3")


def test_revoked_original_source_is_unknown_on_read_without_search_or_writes(
    tmp_path, monkeypatch, capsys
):
    from chess_coach.cli import main
    from chess_coach.evidence_review import review_evidence
    from chess_coach.style_schedule_status import status
    from tests.purpose_browser_fixtures import app, browser_get

    db, learner, position_id, evidence = fixture(tmp_path / "revoked.sqlite", monkeypatch)
    force_control(monkeypatch, position_id, False)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda *_a, **_k: SyntheticEngine())
    result = process_schedule(
        db,
        PipelineConfig(learner=learner, engine_path=sys.executable),
        deadline=time.monotonic() + 25,
    )
    assert status(db, learner)["protection"]["source_state"] == "current"
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_a, **_k: pytest.fail("GET searched")
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(tmp_path / "revoked.sqlite"),
            "style-choices",
            "--learner",
            learner,
        ],
    )
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["purpose_schedule"]["protection"]["evidence_id"] == evidence
    client = app(tmp_path / "revoked.sqlite", subject=learner).test_client()
    page = browser_get(client, "/style-choices")
    assert page.status_code == 200
    assert b"Protection allocation:" in page.data
    assert f"evidence {evidence}".encode() in page.data
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    changes = db.connection.total_changes
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_a, **_k: pytest.fail("GET searched")
    )
    view = status(db, learner)["protection"]
    assert view["state"] == "unknown"
    assert view.get("source_state") != "current"
    assert db.connection.total_changes == changes
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    assert result["cycle_id"] is not None
    db.close()


def test_three_slots_share_one_history_budget_including_discovery(monkeypatch):
    from types import SimpleNamespace

    import chess_coach.style_schedule_budget as budgets
    import chess_coach.style_schedule_worker as worker

    monkeypatch.setattr(budgets, "LIMIT", 6)
    monkeypatch.setattr(worker, "create_cycle", lambda *_args: (budgets.consume(), 1)[1])
    monkeypatch.setattr(worker, "reconcile", lambda *_args: budgets.consume())
    slots = [{"kind": kind} for kind in ("target", "control", "protection")]
    monkeypatch.setattr(worker, "pending", lambda *_args: slots)
    monkeypatch.setattr(worker, "pending_count", lambda *_args: 1)

    def dispatch(_db, _config, slot, _deadline):
        try:
            budgets.consume()
            budgets.consume()
            return {"slot": slot["kind"], "status": "complete"}
        except budgets.BudgetExceeded:
            return {"slot": slot["kind"], "status": "unknown", "detail": "history_budget"}

    monkeypatch.setattr(worker, "dispatch", dispatch)
    result = worker.process_schedule(
        None, SimpleNamespace(learner="synthetic"), deadline=time.monotonic() + 20
    )
    assert [item["status"] for item in result["processed"]] == ["complete", "complete", "unknown"]
    assert result["processed"][-1]["detail"] == "history_budget"
    assert result["history_used"] == result["history_limit"] == 6
    assert result["status"] == "partial"
    assert budgets.CURRENT.get() is None


def test_schema31_upgrade_is_atomic_and_preserves_legacy_rows(monkeypatch):
    from chess_coach import db_recent
    from chess_coach.db import Database
    from chess_coach.ingest import ingest_pgn
    from tests.purpose_db_snapshot import schema_objects, typed_rows
    from tests.test_style_schedule import CHECK

    add = db_recent.add_protection_schedule
    monkeypatch.setattr(db_recent, "add_protection_schedule", lambda _connection: None)
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, CHECK)
    db.connection.execute("PRAGMA user_version=30")
    db.connection.commit()
    objects = schema_objects(db)
    tables = [row[1] for row in objects if row[0] == "table"]
    rows = typed_rows(db, tables)

    def fail_after_schema(connection):
        add(connection)
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(db_recent, "add_protection_schedule", fail_after_schema)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 30
    assert schema_objects(db) == objects
    assert typed_rows(db, tables) == rows
    monkeypatch.setattr(db_recent, "add_protection_schedule", add)
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 31
    assert schema_objects(db) >= objects
    assert typed_rows(db, tables) == rows
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()
    db.close()


def test_protection_rotation_advances_independently_and_covers_candidates():
    from chess_coach.db import Database
    from chess_coach.ingest import ingest_pgn
    from chess_coach.style_protection_schedule_rotation import advance, choose
    from tests.test_style_schedule import CHECK

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, CHECK)
    candidates = [{"game_id": 1, "position_id": item} for item in range(1, 101)]
    seen = []
    for _ in candidates:
        seen.append(choose(db, "synthetic", candidates)["position_id"])
        advance(db, "synthetic", 1)
    assert len(set(seen)) == 100
    assert db.connection.execute("SELECT COUNT(*) FROM style_schedule_rotation").fetchone()[0] == 0
    db.close()


def test_native_work_reports_overshoot_and_unknown_without_summing_multipv():
    from chess_coach.style_schedule_work_summary import summary

    items = [
        {
            "work": {
                "searches": [{"requested_nodes": 50000, "actual_nodes": 51000, "overshoot": True}],
                "unknown": False,
            }
        },
        {
            "work": {
                "searches": [{"requested_nodes": 200000, "actual_nodes": None, "overshoot": None}],
                "unknown": True,
            }
        },
    ]
    result = summary(items)
    assert result["searches_observed"] == 2
    assert result["requested_nodes_observed_lower_bound"] == 250000
    assert result["actual_nodes_observed_lower_bound"] == 51000
    assert result["searches_with_overshoot"] == 1
    assert result["work_unknown"] is True
