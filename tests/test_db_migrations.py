from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from chess_coach import db_migrations
from chess_coach.db import SCHEMA, Database
from chess_coach.mastery import update_mastery


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
    observation_column: bool,
) -> None:
    db = legacy_database(observation_column=observation_column)
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
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 1
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


def test_unknown_time_does_not_enter_trend() -> None:
    db = legacy_database()
    db.initialize()
    old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    recent = datetime.now(UTC).isoformat()
    db.connection.executemany(
        "INSERT INTO evidence_mappings (skill, operation, outcome, confidence, human_validated, observation_at) "
        "VALUES ('fork', 'execute', ?, 1, 1, ?)",
        [("failure", old), ("success", recent)],
    )
    db.connection.commit()
    state = update_mastery(db, skill="fork", operation="execute")
    assert state is not None
    assert state["trend_30d"] == 1.0


def test_future_schema_and_pending_transactions_are_not_modified() -> None:
    db = Database(":memory:")
    db.connection.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="unsupported schema version"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 99
    db.connection.execute("PRAGMA user_version = 0")
    db.connection.execute("CREATE TABLE test (value TEXT)")
    db.connection.execute("INSERT INTO test VALUES ('uncommitted')")
    with pytest.raises(RuntimeError, match="existing transaction"):
        db.initialize()
    db.connection.rollback()
    assert db.connection.execute("SELECT COUNT(*) FROM test").fetchone()[0] == 0


def test_original_schema_with_missing_columns_upgrades() -> None:
    db = Database(":memory:")
    legacy = SCHEMA
    start = legacy.index("CREATE TABLE IF NOT EXISTS evidence_mappings (")
    end = legacy.index(");", start)
    evidence = legacy[start:end]
    for line in (
        "    human_validated INTEGER NOT NULL DEFAULT 0,\n",
        "    context_json TEXT NOT NULL DEFAULT '{}',\n",
        "    subject TEXT NOT NULL DEFAULT 'default',\n",
        "    observation_at TEXT DEFAULT CURRENT_TIMESTAMP,\n",
    ):
        evidence = evidence.replace(line, "")
    legacy = legacy[:start] + evidence + legacy[end:]
    for line in (
        "    variant TEXT NOT NULL DEFAULT 'Standard', termination TEXT,\n",
        "    binary_path TEXT NOT NULL DEFAULT '',\n",
        "    binary_version TEXT NOT NULL DEFAULT '',\n",
        "    nnue TEXT NOT NULL DEFAULT '',\n",
        "    compatibility_json TEXT NOT NULL DEFAULT '{}',\n",
        "    multipv INTEGER NOT NULL DEFAULT 1,\n",
        "    conditioning_elo INTEGER,\n",
    ):
        legacy = legacy.replace(line, "")
    db.connection.executescript(legacy)
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('original', 'A', 'B', '*')"
    )
    db.connection.execute(
        "INSERT INTO evidence_mappings (skill, operation, outcome, confidence) "
        "VALUES ('fork', 'execute', 'ambiguous', 1)"
    )
    db.connection.commit()
    db.initialize()
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == "original"
    evidence = db.connection.execute(
        "SELECT human_validated, context_json, subject, observation_at FROM evidence_mappings"
    ).fetchone()
    assert tuple(evidence) == (0, "{}", "default", None)
    fresh = Database(":memory:")
    fresh.initialize()
    assert schema_columns(db) == schema_columns(fresh)


def test_legacy_update_mastery_cli_handles_unknown_timestamp(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    from chess_coach.cli import main

    db = legacy_database()
    target = Database(tmp_path / "legacy.sqlite")
    db.connection.backup(target.connection)
    target.close()
    monkeypatch.setattr(
        "sys.argv",
        [
            "chess-coach",
            "--db",
            str(tmp_path / "legacy.sqlite"),
            "update-mastery",
            "fork",
            "execute",
        ],
    )
    main()
    assert '"skill": "fork"' in capsys.readouterr().out


def test_external_foreign_key_prevents_destructive_rebuild() -> None:
    db = legacy_database()
    db.connection.execute(
        "CREATE TABLE custom (evidence_id INTEGER REFERENCES evidence_mappings(id) ON DELETE CASCADE)"
    )
    db.connection.execute("INSERT INTO custom VALUES (1)")
    db.connection.commit()
    with pytest.raises(RuntimeError, match="external foreign keys"):
        db.initialize()
    assert db.connection.execute("SELECT * FROM custom").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 1
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 0


def test_upgrade_preserves_custom_evidence_index_and_trigger() -> None:
    db = legacy_database()
    db.connection.executescript("""
        CREATE TABLE evidence_audit (evidence_id INTEGER, outcome TEXT);
        CREATE INDEX custom_evidence_outcome ON evidence_mappings (skill, outcome);
        CREATE TRIGGER custom_evidence_insert AFTER INSERT ON evidence_mappings
        BEGIN
            INSERT INTO evidence_audit (evidence_id, outcome) VALUES (NEW.id, NEW.outcome);
        END;
    """)
    before = {
        row["name"]: row["sql"]
        for row in db.connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE name IN (?, ?)",
            ("custom_evidence_outcome", "custom_evidence_insert"),
        )
    }
    assert len(before) == 2
    db.initialize()
    db.initialize()
    after = {
        row["name"]: row["sql"]
        for row in db.connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE name IN (?, ?)",
            ("custom_evidence_outcome", "custom_evidence_insert"),
        )
    }
    assert after == before
    assert [
        row["name"] for row in db.connection.execute("PRAGMA index_info(custom_evidence_outcome)")
    ] == ["skill", "outcome"]
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_audit").fetchone()[0] == 0
    cursor = db.connection.execute(
        "INSERT INTO evidence_mappings (skill, operation, outcome, confidence) "
        "VALUES ('pin', 'execute', 'failure', 1)"
    )
    audit = db.connection.execute("SELECT evidence_id, outcome FROM evidence_audit").fetchone()
    assert tuple(audit) == (cursor.lastrowid, "failure")
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
