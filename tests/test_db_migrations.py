from __future__ import annotations

import sqlite3

import pytest

from chess_coach import db_migrations
from chess_coach.db import SCHEMA, Database
from chess_coach.db_versioning import CURRENT_VERSION


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
    observation_column: bool, tmp_path, monkeypatch
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
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_VERSION
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
    _fork_index_upgrade(monkeypatch)
    _public_mate_index_upgrade(monkeypatch)
    _native_upgrade_inventory(tmp_path, monkeypatch)
    _position_index_upgrade()
    _current_schema_contention(tmp_path)


def _native_upgrade_inventory(tmp_path, monkeypatch):
    from chess_coach.analysis_schema import add_decision_columns
    from chess_coach.db_recent import upgrade_recent
    from chess_coach.lichess_schema import add_sync_progress
    from chess_coach.native_upgrade_build import supported
    from chess_coach.native_upgrade_plan import plan
    from chess_coach.recovery_gzip import compressed_recovery

    path = tmp_path / "native-upgrade-inventory.sqlite"
    db = Database(path)
    db.connection.execute("BEGIN")
    db_migrations.upgrade_v1(db.connection, SCHEMA)
    add_decision_columns(db.connection)
    add_sync_progress(db.connection)
    upgrade_recent(db.connection, 3, through=32)
    db.connection.execute(
        "INSERT INTO games(source_id,pgn,white,black,result) VALUES('sample','synthetic','A','B','*')"
    )
    db.connection.execute(
        "INSERT INTO positions(game_id,ply,fen,san,uci) VALUES(1,1,'fen','a','a1a2')"
    )
    db.connection.execute(
        "INSERT INTO analysis_runs(game_id,engine,engine_version,config_json) VALUES(1,'fixture','v1','{}')"
    )
    db.connection.execute("INSERT INTO engine_outputs(run_id,position_id) VALUES(1,1)")
    db.connection.executemany(
        "INSERT INTO training_items(source_type,source_ref,skill,operation,due,scheduler_version) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("puzzle", "mate", "mate_in_one", "execute", "2026-01-01", "v1"),
            ("unified_owned_capture", "capture", "hanging_piece", "execute", "2026-01-01", "v1"),
            ("unified_owned_fork", "fork", "fork", "execute", "2026-01-01", "v1"),
            ("unified_public_m1", "public", "mate_in_one", "execute", "2026-01-01", "v1"),
        ],
    )
    db.connection.execute("ANALYZE")
    db.connection.commit()
    db.close()
    original = path.read_bytes()

    import subprocess
    import sys

    from chess_coach import native_upgrade_plan

    def exclusive():
        script = """
import sqlite3, sys
connection = sqlite3.connect(sys.argv[1], timeout=0)
try:
    connection.execute("BEGIN EXCLUSIVE")
except sqlite3.OperationalError as exc:
    assert exc.sqlite_errorcode == sqlite3.SQLITE_BUSY
    print("blocked")
else:
    connection.rollback()
    print("acquired")
finally:
    connection.close()
"""
        return subprocess.run(
            [sys.executable, "-c", script, str(path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()

    observed = []
    real_inspect = native_upgrade_plan.inspect_layout

    def inspect_while_pinned(*args):
        layout = real_inspect(*args)
        observed.append(exclusive())
        return layout

    with monkeypatch.context() as patch:
        patch.setattr(native_upgrade_plan, "inspect_layout", inspect_while_pinned)
        result = plan(path, tmp_path)
    with sqlite3.connect(":memory:") as probe:
        if not supported(probe):
            assert result == {"status": "unknown", "inventory_complete": False}
            assert path.read_bytes() == original
            return
    assert result["status"] == "unknown" and result["inventory_complete"]
    assert observed == ["blocked"]
    assert exclusive() == "acquired"
    assert (
        result["engine_rows"],
        result["mate_rows"],
        result["capture_rows"],
        result["fork_rows"],
        result["public_mate_rows"],
    ) == (1, 1, 1, 1, 1)
    assert result["target_schema"] == CURRENT_VERSION
    assert result["source_index_rows"] == result["source_due_rows"] == 4
    assert result["source_type_max_bytes"] == len("unified_owned_capture")
    assert result["skill_max_bytes"] == len("hanging_piece")
    assert result["operation_max_bytes"] == len("execute")
    assert result["due_max_bytes"] == len("2026-01-01")
    assert result["page_size"] == 4096 and result["metadata_pages"] > 0
    assert result["metadata_pages"] <= result["metadata_sector_pages"] <= result["page_count"]
    assert path.read_bytes() == original

    import json

    command = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "chess_coach.native_upgrade_check",
            str(path),
            "--project-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    inspected = json.loads(command.stdout)
    assert inspected["status"] == "unknown" and inspected["inventory_complete"]
    assert inspected["process_address_limit_bytes"] == 1024 * 1024 * 1024
    assert inspected["sqlite_hard_heap_limit_bytes"] == 512 * 1024 * 1024
    assert path.read_bytes() == original
    archive = tmp_path / "native-backup.gz"
    restored = tmp_path / "native-restore.sqlite"
    assert compressed_recovery(path, archive, restored, project_root=tmp_path) == {
        "status": "verified"
    }
    recovered = plan(path, tmp_path, archive=archive, restored=restored)
    assert recovered["status"] == "unknown" and recovered["recovery_current"]

    # An aliased manifest must be refused before opening it under the source pin.
    import os

    aliased_archive = tmp_path / "aliased-backup.gz"
    aliased_archive.write_bytes(b"synthetic")
    os.link(path, aliased_archive.with_name(aliased_archive.name + ".manifest.json"))
    observed.clear()
    real_recovery = native_upgrade_plan.check_recovery

    def check_while_pinned(*args, **kwargs):
        try:
            return real_recovery(*args, **kwargs)
        finally:
            observed.append(exclusive())

    with monkeypatch.context() as patch:
        patch.setattr(native_upgrade_plan, "check_recovery", check_while_pinned)
        refused = plan(path, tmp_path, archive=aliased_archive, restored=restored)
    assert refused == {"status": "unknown", "inventory_complete": False}
    assert observed == ["blocked"]
    assert exclusive() == "acquired"

    zstd_archive = tmp_path / "native-backup.zst"
    zstd_restore = tmp_path / "native-zstd-restore.sqlite"
    assert compressed_recovery(
        path, zstd_archive, zstd_restore, project_root=tmp_path, codec="zstd"
    ) == {"status": "verified"}
    zstd_plan = plan(path, tmp_path, archive=zstd_archive, restored=zstd_restore, codec="zstd")
    assert zstd_plan["status"] == "unknown" and zstd_plan["recovery_current"]
    verified_command = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "chess_coach.native_upgrade_check",
            str(path),
            "--project-root",
            str(tmp_path),
            "--archive",
            str(zstd_archive),
            "--restored",
            str(zstd_restore),
            "--codec",
            "zstd",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    checked = json.loads(verified_command.stdout)
    assert (
        checked["recovery_current"] and checked["sqlite_hard_heap_limit_bytes"] == 512 * 1024 * 1024
    )

    import gzip
    import hashlib

    manifest_path = archive.with_name(archive.name + ".manifest.json")
    previous_archive, previous_manifest = archive.read_bytes(), manifest_path.read_bytes()
    different = gzip.compress(b"different synthetic content")
    manifest = json.loads(previous_manifest)
    manifest["archive_bytes"] = len(different)
    manifest["archive_sha256"] = hashlib.sha256(different).hexdigest()
    archive.write_bytes(different)
    manifest_path.write_text(json.dumps(manifest))
    assert plan(path, tmp_path, archive=archive, restored=restored) == {
        "status": "unknown",
        "inventory_complete": False,
    }
    archive.write_bytes(previous_archive)
    manifest_path.write_bytes(previous_manifest)

    limited = Database(path)
    pages = limited.connection.execute("PRAGMA page_count").fetchone()[0]
    assert limited.connection.execute(f"PRAGMA max_page_count={pages}").fetchone()[0] == pages
    with pytest.raises(sqlite3.OperationalError) as failure:
        limited.initialize()
    assert failure.value.sqlite_errorcode == sqlite3.SQLITE_FULL
    assert limited.connection.execute("PRAGMA user_version").fetchone()[0] == 32
    assert limited.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert limited.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert limited.connection.execute("SELECT count(*) FROM engine_outputs").fetchone()[0] == 1
    limited.close()
    assert path.read_bytes() == original

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("UPDATE engine_outputs SET position_id='invalid'")
    assert plan(path, tmp_path) == {"status": "unknown", "inventory_complete": False}


def _fork_index_upgrade(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    db.initialize()
    connection = db.connection
    connection.executemany(
        "INSERT INTO training_items(source_type,source_ref,skill,operation,due,scheduler_version) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("unified_owned_fork", "first", "fork", "execute", "2026-01-01", "v1"),
            ("unified_owned_fork", "second", "fork", "execute", "2026-01-01", "v1"),
            ("unified_owned_fork", "future", "fork", "execute", "2027-01-01", "v1"),
            ("unified_owned_fork", "now", "fork", "execute", "now", "v1"),
            ("unified_owned_fork", "wrong-operation", "fork", "prevent", "2020-01-01", "v1"),
            ("unified_owned_fork", "wrong-skill", "mate", "execute", "2020-01-01", "v1"),
            ("puzzle", "other", "fork", "execute", "2020-01-01", "v1"),
        ],
    )
    connection.execute(
        "INSERT INTO training_attempts(item_id,rating,reviewed_at,scheduler_version) "
        "VALUES (1,'good','2026-01-01','v1')"
    )
    connection.execute("DROP INDEX idx_curriculum_fork_due")
    connection.execute("DROP INDEX idx_curriculum_fork_scheduled")
    connection.execute("PRAGMA user_version=39")
    connection.commit()
    before_schema = [
        tuple(row)
        for row in connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )
    ]
    before_rows = {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in ("training_items", "training_attempts")
    }
    original = db_recent.add_fork_indexes

    def fail_after_indexes(conn):
        original(conn)
        raise RuntimeError("injected index failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_fork_indexes", fail_after_indexes)
        with pytest.raises(RuntimeError, match="injected index failure"):
            db.initialize()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 39
    assert [
        tuple(row)
        for row in connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )
    ] == before_schema
    db.initialize()
    db.initialize()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_VERSION
    assert [
        tuple(row)
        for row in connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT IN ('idx_curriculum_fork_due','idx_curriculum_fork_scheduled') "
            "ORDER BY type,name"
        )
    ] == before_schema
    assert {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in before_rows
    } == before_rows
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    due = (
        "SELECT id FROM training_items INDEXED BY idx_curriculum_fork_due "
        "WHERE source_type='unified_owned_fork' AND skill='fork' AND operation='execute' "
        "AND lower(due) != 'now' AND julianday(due) <= julianday(?) "
        "ORDER BY julianday(due),id LIMIT ?"
    )
    scheduled = (
        "SELECT id FROM training_items INDEXED BY idx_curriculum_fork_scheduled "
        "WHERE id>? AND source_type='unified_owned_fork' AND skill='fork' "
        "AND operation='execute' ORDER BY id LIMIT ?"
    )
    assert [row[0] for row in connection.execute(due, ("2026-02-01", 10))] == [1, 2]
    assert [row[0] for row in connection.execute(scheduled, (0, 10))] == [1, 2, 3, 4]
    for query, args, index in (
        (due, ("2026-02-01", 10), "idx_curriculum_fork_due"),
        (scheduled, (0, 10), "idx_curriculum_fork_scheduled"),
    ):
        plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + query, args)]
        assert any(index in detail for detail in plan)
        assert not any("TEMP B-TREE" in detail for detail in plan)
    db.close()


def _public_mate_index_upgrade(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    db.initialize()
    connection = db.connection
    connection.executemany(
        "INSERT INTO training_items(source_type,source_ref,skill,operation,due,scheduler_version) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("unified_public_m1", "public-a", "mate_in_one", "execute", "2026-01-01", "v1"),
            ("unified_public_m1", "public-b", "mate_in_one", "execute", "2027-01-01", "v1"),
            ("fixture_canonical", "canonical", "promotion", "execute", "2026-01-01", "v1"),
        ],
    )
    connection.execute("DROP INDEX idx_curriculum_source_due")
    connection.execute("DROP INDEX idx_curriculum_source_scheduled")
    connection.execute("PRAGMA user_version=40")
    connection.commit()
    before = [tuple(row) for row in connection.execute("SELECT * FROM training_items ORDER BY id")]
    original = db_recent.add_public_mate_indexes

    def fail_after_indexes(conn):
        original(conn)
        raise RuntimeError("injected public index failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_public_mate_indexes", fail_after_indexes)
        with pytest.raises(RuntimeError, match="injected public index failure"):
            db.initialize()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 40
    assert not connection.execute(
        "SELECT name FROM sqlite_master WHERE name IN ('idx_curriculum_source_due','idx_curriculum_source_scheduled')"
    ).fetchall()
    db.initialize()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_VERSION
    assert [
        tuple(row) for row in connection.execute("SELECT * FROM training_items ORDER BY id")
    ] == before
    due = (
        "SELECT id FROM training_items INDEXED BY idx_curriculum_source_due "
        "WHERE source_type='unified_public_m1' AND skill='mate_in_one' AND operation='execute' "
        "AND lower(due) != 'now' AND julianday(due) <= julianday(?) "
        "ORDER BY julianday(due),id LIMIT ?"
    )
    scheduled = (
        "SELECT id FROM training_items INDEXED BY idx_curriculum_source_scheduled "
        "WHERE id>? AND source_type='unified_public_m1' AND skill='mate_in_one' "
        "AND operation='execute' ORDER BY id LIMIT ?"
    )
    assert [row[0] for row in connection.execute(due, ("2026-02-01", 10))] == [1]
    assert [row[0] for row in connection.execute(scheduled, (0, 10))] == [1, 2]
    canonical_due = due.replace("unified_public_m1", "fixture_canonical").replace(
        "mate_in_one", "promotion"
    )
    canonical_scheduled = scheduled.replace("unified_public_m1", "fixture_canonical").replace(
        "mate_in_one", "promotion"
    )
    assert [row[0] for row in connection.execute(canonical_due, ("2026-02-01", 10))] == [3]
    assert [row[0] for row in connection.execute(canonical_scheduled, (0, 10))] == [3]
    for query, args, index in (
        (due, ("2026-02-01", 10), "idx_curriculum_source_due"),
        (scheduled, (0, 10), "idx_curriculum_source_scheduled"),
        (canonical_due, ("2026-02-01", 10), "idx_curriculum_source_due"),
        (canonical_scheduled, (0, 10), "idx_curriculum_source_scheduled"),
    ):
        plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + query, args)]
        assert any(index in detail for detail in plan)
        assert not any("TEMP B-TREE" in detail for detail in plan)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    # A failed source-id index upgrade must leave the native-41 database intact.
    connection.executemany(
        "INSERT INTO games(source,source_id,pgn,white,black,result) VALUES(?,?,?,?,?,?)",
        [
            ("fixture-a", "same-source-id", "*", "learner", "other", "*"),
            ("fixture-b", "same-source-id", "*", "other", "learner", "*"),
        ],
    )
    connection.execute("DROP INDEX idx_games_source_id")
    connection.execute("PRAGMA user_version=41")
    connection.commit()
    original_game_index = db_recent.add_game_source_index

    def fail_after_game_index(conn):
        original_game_index(conn)
        raise RuntimeError("injected game index failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_game_source_index", fail_after_game_index)
        with pytest.raises(RuntimeError, match="injected game index failure"):
            db.initialize()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 41
    assert not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_games_source_id'"
    ).fetchone()
    db.initialize()
    query = (
        "SELECT source FROM games INDEXED BY idx_games_source_id "
        "WHERE source_id=? AND (lower(white)=? OR lower(black)=?) ORDER BY source"
    )
    assert [
        row[0] for row in connection.execute(query, ("same-source-id", "learner", "learner"))
    ] == [
        "fixture-a",
        "fixture-b",
    ]
    assert any(
        "idx_games_source_id" in row[3]
        for row in connection.execute(
            "EXPLAIN QUERY PLAN " + query, ("same-source-id", "learner", "learner")
        )
    )
    assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_VERSION
    db.close()


def _position_index_upgrade():
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import tactical_input

    db = Database(":memory:")
    db.initialize()
    connection = db.connection
    connection.executemany(
        "INSERT INTO games (source_id,pgn,white,black,result) VALUES (?, ?, ?, ?, ?)",
        [("first", "synthetic", "A", "B", "*"), ("second", "synthetic", "C", "D", "*")],
    )
    connection.executemany(
        "INSERT INTO positions (game_id,ply,fen,san,uci) VALUES (?,?,?,?,?)",
        [(1, 1, "fen1", "a", "a1a2"), (1, 2, "fen2", "b", "b1b2"), (2, 1, "fen3", "c", "c1c2")],
    )
    connection.executemany(
        "INSERT INTO analysis_runs (game_id,engine,engine_version,config_json) VALUES (?,?,?,?)",
        [(1, "fixture", "v1", "{}"), (2, "fixture", "v1", "{}")],
    )
    connection.executemany(
        "INSERT INTO engine_outputs (id,run_id,position_id,best_move,decision_fen,score_pov,multipv) VALUES (?,?,?,?,?,?,?)",
        [
            (11, 2, 2, "a2a3", "first", "white", 1),
            (4, 1, 1, "b2b3", "second", "black", 1),
            (8, 1, 3, "c2c3", "third", "white", 1),
            (7, 2, 1, "d2d3", "fourth", "black", 2),
        ],
    )
    connection.execute("DROP INDEX IF EXISTS idx_engine_outputs_position_id")
    connection.execute("PRAGMA user_version=35")
    connection.commit()
    before = {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in ("analysis_runs", "positions", "engine_outputs")
    }
    config = PipelineConfig(learner="fixture")
    hashes = [tactical_input(db, game, "fixture-hash", config, 1) for game in (1, 2)]
    db.initialize()
    db.initialize()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_VERSION
    assert {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in before
    } == before
    assert [tactical_input(db, game, "fixture-hash", config, 1) for game in (1, 2)] == hashes
    query = (
        "SELECT e.id,e.position_id,e.best_move,e.decision_fen,e.score_pov,e.multipv "
        "FROM engine_outputs e JOIN positions p ON p.id=e.position_id "
        "WHERE p.game_id=? ORDER BY e.id"
    )
    assert [row[0] for row in connection.execute(query, (1,))] == [4, 7, 11]
    assert [row[0] for row in connection.execute(query, (2,))] == [8]
    plan = connection.execute("EXPLAIN QUERY PLAN " + query, (1,)).fetchall()
    assert any("idx_engine_outputs_position_id" in row[3] for row in plan)
    db.close()


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

    # A failed v36 index creation preserves schema 35 and existing rows.
    monkeypatch.setattr(db_recent, "add_digest_storage", add_digests)
    recent.initialize()
    recent.connection.execute(
        "INSERT INTO games (source_id,pgn,white,black,result) VALUES (?,?,?,?,?)",
        ("rollback", "synthetic", "A", "B", "*"),
    )
    recent.connection.execute(
        "INSERT INTO positions (game_id,ply,fen,san,uci) VALUES (1,1,?,?,?)",
        ("fen", "a", "a1a2"),
    )
    recent.connection.execute(
        "INSERT INTO analysis_runs (game_id,engine,engine_version,config_json) VALUES (1,?,?,?)",
        ("fixture", "v1", "{}"),
    )
    recent.connection.execute(
        "INSERT INTO engine_outputs (run_id,position_id,score_cp) VALUES (1,1,17)"
    )
    recent.connection.execute("DROP INDEX idx_engine_outputs_position_id")
    recent.connection.execute("PRAGMA user_version=35")
    recent.connection.commit()
    before_rows = {
        table: rows(recent, table)
        for table in ("games", "positions", "analysis_runs", "engine_outputs")
    }
    before_v36 = list(
        recent.connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")
    )
    add_position_index = db_recent.add_engine_output_position_index

    def fail_after_position_index(connection):
        add_position_index(connection)
        raise RuntimeError("injected position index migration failure")

    monkeypatch.setattr(db_recent, "add_engine_output_position_index", fail_after_position_index)
    with pytest.raises(RuntimeError, match="position index migration failure"):
        recent.initialize()
    assert recent.connection.execute("PRAGMA user_version").fetchone()[0] == 35
    assert (
        list(
            recent.connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")
        )
        == before_v36
    )
    assert {table: rows(recent, table) for table in before_rows} == before_rows
