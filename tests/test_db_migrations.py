from __future__ import annotations

import sqlite3

import pytest

from chess_coach import db_migrations
from chess_coach.db import SCHEMA, Database


def legacy_database(*, observation_column: bool = False) -> Database:
    db = Database(":memory:")
    schema = SCHEMA.replace("    variant TEXT NOT NULL DEFAULT 'Standard', termination TEXT,\n", "")
    if not observation_column:
        schema = schema.replace("    observation_at TEXT DEFAULT CURRENT_TIMESTAMP,\n", "")
    db.connection.executescript(schema)
    db.connection.execute(
        "INSERT INTO games (source_id, pgn, white, black, result) VALUES ('id', 'raw PGN', 'A', 'B', '*')"
    )
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (1, 1, 'fen', 'e4', 'e2e4')"
    )
    db.connection.execute(
        "INSERT INTO evidence_mappings (position_id, skill, operation, outcome, confidence, human_validated) "
        "VALUES (1, 'fork', 'execute', 'success', 0.8, 1)"
    )
    db.connection.execute(
        "INSERT INTO training_items (source_type, source_ref, skill, operation, due, scheduler_version) "
        "VALUES ('puzzle', 'p1', 'fork', 'execute', '2020-01-01', 'v1')"
    )
    db.connection.execute(
        "INSERT INTO training_attempts (item_id, rating, reviewed_at, scheduler_version) "
        "VALUES (1, 'good', '2020-01-02', 'v1')"
    )
    if observation_column:
        db.connection.execute(
            "UPDATE evidence_mappings SET observation_at = '2020-01-03T00:00:00+00:00'"
        )
    db.connection.commit()
    return db


def rows(db: Database, table: str) -> list[dict]:
    return [dict(row) for row in db.connection.execute(f"SELECT * FROM {table} ORDER BY id")]


def schema_columns(db: Database) -> dict[str, dict[str, tuple]]:
    tables = db.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return {
        table[0]: {
            col[1]: tuple(col)[2:]
            for col in db.connection.execute(f"PRAGMA table_info({table[0]})")
        }
        for table in tables
    }


@pytest.mark.parametrize("observation_column", [False, True])
def test_populated_legacy_upgrade_is_repeatable_and_preserves_history(
    observation_column: bool, tmp_path
) -> None:
    db = legacy_database(observation_column=observation_column)
    db.connection.execute(
        "INSERT INTO analysis_runs(game_id,engine,engine_version,config_json,nnue,compatibility_json) VALUES(1,'legacy','v1',?, ?, ?)",
        ('{"nodes": 17}', '{"net": "old"}', '{"cpu": true}'),
    )
    db.connection.commit()
    old_run = dict(db.connection.execute("SELECT * FROM analysis_runs").fetchone())
    old_columns = [tuple(row) for row in db.connection.execute("PRAGMA table_info(analysis_runs)")]
    preserved = {
        table: rows(db, table)
        for table in (
            "games",
            "positions",
            "evidence_mappings",
            "training_items",
            "training_attempts",
        )
    }
    db.initialize()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 35
    assert dict(db.connection.execute("SELECT * FROM analysis_runs").fetchone()) == old_run
    assert dict(db.connection.execute("SELECT * FROM analysis_runs_read").fetchone()) == old_run
    assert (
        db.connection.execute("SELECT compact FROM analysis_provenance_settings").fetchone()[0] == 0
    )
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_run_provenance").fetchone()[0] == 0
    assert [
        tuple(row) for row in db.connection.execute("PRAGMA table_info(analysis_runs)")
    ] == old_columns
    # With compact writes off and no links, a legacy writer sees the same table shape.
    db.connection.execute("PRAGMA user_version=32")
    db.connection.execute(
        "INSERT INTO analysis_runs(game_id,engine,engine_version,config_json) VALUES(1,'old','v1','{}')"
    )
    db.connection.commit()
    db.initialize()
    assert [
        dict(row) for row in db.connection.execute("SELECT * FROM analysis_runs ORDER BY id")
    ] == [
        dict(row) for row in db.connection.execute("SELECT * FROM analysis_runs_read ORDER BY id")
    ]
    # Simulate a fully initialized schema-33 archive using the documented direct API.
    from chess_coach.fact_runs import record_fact_run, record_fact_run_in_transaction

    db.connection.execute("DROP VIEW detector_runs_read")
    db.connection.execute("DROP TABLE detector_input_settings")
    db.connection.execute("DROP TABLE detector_inputs")
    db.connection.execute("PRAGMA user_version=33")
    db.connection.commit()
    args = {
        "position_id": 1,
        "producer": "legacy-direct",
        "detector_version": "v1",
        "input_data": {"sample": "original"},
        "facts": [{"fact_type": "fixture", "payload": {"note": "original"}}],
    }
    old = record_fact_run(db, **args)
    assert record_fact_run(db, **args) == {**old, "replayed": True}
    db.connection.execute("BEGIN IMMEDIATE")
    assert record_fact_run_in_transaction(db, **args) == {**old, "replayed": True}
    db.connection.commit()
    detector_before = dict(
        db.connection.execute("SELECT * FROM detector_runs WHERE id=?", (old["run_id"],)).fetchone()
    )
    detector_columns = [
        tuple(row) for row in db.connection.execute("PRAGMA table_info(detector_runs)")
    ]
    db.connection.execute(
        "CREATE TABLE detector_inputs(input_hash TEXT PRIMARY KEY, input_json TEXT NOT NULL) WITHOUT ROWID"
    )
    with pytest.raises(ValueError, match="detector input schema unavailable"):
        record_fact_run(db, **args)
    db.connection.execute("DROP TABLE detector_inputs")
    db.initialize()
    assert (
        dict(
            db.connection.execute(
                "SELECT * FROM detector_runs WHERE id=?", (old["run_id"],)
            ).fetchone()
        )
        == detector_before
    )
    assert (
        dict(
            db.connection.execute(
                "SELECT * FROM detector_runs_read WHERE id=?", (old["run_id"],)
            ).fetchone()
        )
        == detector_before
    )
    assert [
        tuple(row) for row in db.connection.execute("PRAGMA table_info(detector_runs)")
    ] == detector_columns
    assert db.connection.execute("SELECT compact FROM detector_input_settings").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM detector_inputs").fetchone()[0] == 0
    assert record_fact_run(db, **args) == {**old, "replayed": True}
    for table, old_rows in preserved.items():
        new_rows = rows(db, table)
        assert [
            {key: row[key] for key in old} for row, old in zip(new_rows, old_rows, strict=True)
        ] == old_rows
    observed = rows(db, "evidence_mappings")[0]["observation_at"]
    assert observed == ("2020-01-03T00:00:00+00:00" if observation_column else None)
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    fresh = Database(":memory:")
    fresh.initialize()
    assert schema_columns(db) == schema_columns(fresh)
    _current_schema_contention(tmp_path)


def _current_schema_contention(tmp_path):
    from chess_coach.db_versioning import CURRENT_VERSION

    path = tmp_path / "current.sqlite"
    db = Database(path)
    db.initialize()
    db.connection.execute("PRAGMA busy_timeout=0")
    reader = sqlite3.connect(path, timeout=0)
    reader.execute("BEGIN")
    reader.execute("SELECT count(*) FROM sqlite_schema").fetchone()
    statements = []
    db.connection.set_trace_callback(statements.append)
    db.initialize()
    assert not db.connection.in_transaction
    assert not any(sql.upper().startswith(("BEGIN", "COMMIT")) for sql in statements)
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_VERSION

    db.connection.execute("BEGIN")
    with pytest.raises(RuntimeError, match="existing transaction"):
        db.initialize()
    assert db.connection.in_transaction
    db.connection.rollback()
    reader.rollback()

    reader.execute("BEGIN IMMEDIATE")
    db.initialize()
    assert not db.connection.in_transaction
    reader.rollback()
    reader.close()

    db.connection.execute(f"PRAGMA user_version={CURRENT_VERSION - 1}")
    db.connection.commit()
    statements.clear()
    db.initialize()
    statements = [sql.upper() for sql in statements]
    begin = statements.index("BEGIN IMMEDIATE")
    assert statements[:begin].count("PRAGMA USER_VERSION") == 1
    assert "PRAGMA USER_VERSION" in statements[begin + 1 :]
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_VERSION

    db.connection.execute(f"PRAGMA user_version={CURRENT_VERSION + 1}")
    db.connection.commit()
    with pytest.raises(RuntimeError, match="unsupported schema version"):
        db.initialize()
    assert not db.connection.in_transaction
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_VERSION + 1
    db.close()


def test_failed_upgrade_rolls_back_schema_and_data(monkeypatch: pytest.MonkeyPatch) -> None:
    db = legacy_database()
    before_schema = list(
        db.connection.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name")
    )
    before = {
        table: rows(db, table)
        for table in (
            "games",
            "positions",
            "evidence_mappings",
            "training_items",
            "training_attempts",
        )
    }
    original = db_migrations.rebuild_evidence

    def fail_after_rebuild(connection, schema):
        original(connection, schema)
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(db_migrations, "rebuild_evidence", fail_after_rebuild)
    with pytest.raises(RuntimeError, match="injected"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 0
    assert (
        list(db.connection.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name"))
        == before_schema
    )
    assert {table: rows(db, table) for table in before} == before
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []

    # A failed v34 installation also rolls back its new objects and version.
    monkeypatch.setattr(db_migrations, "rebuild_evidence", original)
    from chess_coach import db_recent

    recent = Database(":memory:")
    recent.initialize()
    recent.connection.execute("DROP VIEW detector_runs_read")
    recent.connection.execute("DROP TABLE detector_input_settings")
    recent.connection.execute("DROP TABLE detector_inputs")
    recent.connection.execute("PRAGMA user_version=33")
    recent.connection.commit()
    before_recent = list(
        recent.connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")
    )
    add_inputs = db_recent.add_detector_inputs

    def fail_after_inputs(connection):
        add_inputs(connection)
        raise RuntimeError("injected detector migration failure")

    monkeypatch.setattr(db_recent, "add_detector_inputs", fail_after_inputs)
    with pytest.raises(RuntimeError, match="detector migration failure"):
        recent.initialize()
    assert recent.connection.execute("PRAGMA user_version").fetchone()[0] == 33
    assert (
        list(
            recent.connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")
        )
        == before_recent
    )
    assert recent.connection.execute("PRAGMA foreign_key_check").fetchall() == []

    # A failed v35 transition leaves the v34 detector view and settings intact.
    monkeypatch.setattr(db_recent, "add_detector_inputs", add_inputs)
    recent.initialize()
    recent.connection.execute("DROP VIEW mapping_runs_read")
    recent.connection.execute("DROP TABLE digest_settings")
    recent.connection.execute("DROP VIEW detector_runs_read")
    add_inputs(recent.connection)
    recent.connection.execute("PRAGMA user_version=34")
    recent.connection.commit()
    before_v35 = list(
        recent.connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")
    )
    add_digests = db_recent.add_digest_storage

    def fail_after_digests(connection):
        add_digests(connection)
        raise RuntimeError("injected digest migration failure")

    monkeypatch.setattr(db_recent, "add_digest_storage", fail_after_digests)
    with pytest.raises(RuntimeError, match="digest migration failure"):
        recent.initialize()
    assert recent.connection.execute("PRAGMA user_version").fetchone()[0] == 34
    assert (
        list(
            recent.connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")
        )
        == before_v35
    )
