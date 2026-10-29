"""Upgrade schema 25 through probes 26 and objective verification 27."""

import pytest

from chess_coach import db_recent
from chess_coach.mate_auto import process_decision
from chess_coach.mate_contract import MAPPER
from chess_coach.mate_practice_source import VERSION
from chess_coach.unified_session_events import hint
from chess_coach.unified_sessions import start
from tests.test_mate_proof import owned_game


def old_database(path, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_probes", lambda connection: None)
        patch.setattr(db_recent, "add_objective_verification", lambda connection: None)
        db = owned_game(path, patch)
    db.connection.execute("PRAGMA user_version = 25")
    db.connection.commit()
    process_decision(db, 1, "fixture_a")
    evidence = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()[0]
    start(
        db,
        attempt_id="old",
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )
    hint(db, "old", "fixture_a", event_id="old-hint")
    return db


def snapshot(db):
    return {
        table: [
            tuple(row) for row in db.connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
        ]
        for table in ("unified_sessions", "unified_session_events")
    }


def tables(db):
    return {
        row[0]
        for row in db.connection.execute("SELECT name FROM sqlite_master WHERE type=?", ("table",))
    }


def test_ordered_upgrade_and_rollback_preserve_existing_rows(tmp_path, monkeypatch):
    db = old_database(tmp_path / "schema25.sqlite", monkeypatch)
    before = snapshot(db)
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 25
    assert "diagnostic_probes" not in tables(db) and "objective_requests" not in tables(db)
    original = db_recent.add_objective_verification

    def fail(connection):
        original(connection)
        raise RuntimeError("synthetic migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_objective_verification", fail)
        with pytest.raises(RuntimeError, match="synthetic migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 25
    assert "diagnostic_probes" not in tables(db) and "objective_requests" not in tables(db)
    assert snapshot(db) == before
    db.initialize()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 28
    assert {
        "diagnostic_probes",
        "diagnostic_probe_events",
        "objective_requests",
        "objective_results",
    } <= tables(db)
    assert snapshot(db) == before
    assert not db.connection.execute("PRAGMA foreign_key_check").fetchall()


def test_populated_schema26_probe_history_is_preserved(tmp_path, monkeypatch):
    db = old_database(tmp_path / "schema26.sqlite", monkeypatch)
    db_recent.add_probes(db.connection)
    db.connection.execute("PRAGMA user_version = 26")
    lesson = db.connection.execute(
        "INSERT INTO lesson_versions(subject,lesson_json,generator_model,prompt_version,input_json) VALUES(?,?,?,?,?)",
        ("fixture_a", "{}", "fixture", "fixture-v1", "{}"),
    ).lastrowid
    evidence = db.connection.execute("SELECT id FROM evidence_mappings LIMIT 1").fetchone()[0]
    db.connection.execute(
        "INSERT INTO diagnostic_probes VALUES(?,?,?,?,?,?,?,?)",
        (
            "fixture-probe",
            "fixture_a",
            lesson,
            evidence,
            1,
            "{}",
            "fixture-hash",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    db.connection.execute(
        "INSERT INTO diagnostic_probe_events VALUES(?,?,?,?,?,?)",
        ("fixture-probe", "fixture-event", "answer", "{}", "{}", "2026-01-01T00:00:00+00:00"),
    )
    db.connection.commit()
    before = {
        table: [
            tuple(row) for row in db.connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
        ]
        for table in (
            "diagnostic_probes",
            "diagnostic_probe_events",
            "unified_sessions",
            "unified_session_events",
        )
    }
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 28
    after = {
        table: [
            tuple(row) for row in db.connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
        ]
        for table in before
    }
    assert after == before and not db.connection.execute("PRAGMA foreign_key_check").fetchall()
