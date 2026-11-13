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
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 33
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
