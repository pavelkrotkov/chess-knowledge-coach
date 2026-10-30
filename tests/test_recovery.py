"""SQLite online recovery preserves data and never migrates the source."""

import json
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.fact_runs import record_fact_run
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.mapping_transaction import mapping_transaction
from chess_coach.puzzle_sessions import start_attempt
from chess_coach.recovery import backup_database, restore_database
from chess_coach.training import create_training_item, review_item
from chess_coach.training_feedback import puzzle_training_ref, submit_training_move


def populated_wal(path: Path) -> Database:
    db = Database(path)
    db.initialize()
    assert db.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    db.connection.execute("PRAGMA wal_autocheckpoint=0")
    db.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES ('fixture','A','B','1-0')"
    )
    db.connection.execute(
        "INSERT INTO positions(game_id,ply,fen,san,uci) VALUES (1,1,'fen','e4','e2e4')"
    )
    db.connection.commit()
    facts = record_fact_run(
        db,
        position_id=1,
        producer="fixture",
        detector_version="v1",
        input_data={},
        facts=[{"fact_type": "fork", "payload": {}}],
    )
    with mapping_transaction(db):
        mapped = record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="fixture",
            mapper_version="v1",
            subject="learner",
            operation="execute",
            scope_key="test",
            input_data={},
            mappings=[
                {
                    "skill": "fork",
                    "outcome": "success",
                    "confidence": 1,
                    "fact_ids": facts["fact_ids"],
                    "context": {},
                    "observation_at": None,
                }
            ],
        )
    review_evidence(db, mapped["evidence_ids"][0], decision="accept", actor="fixture-reviewer")
    item = create_training_item(
        db, source_type="canonical", source_ref="fixture", skill="fork", operation="execute"
    )
    review_item(db, item, "good", elapsed_seconds=3)
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v1','fixture','checksum')"
    )
    db.connection.execute("""INSERT INTO puzzles
        (puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES ('p1',1,'6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1','','g8h8 c5f8',1200,80,'[]','execute')""")
    db.connection.commit()
    start_attempt(db, attempt_id="fixture-attempt", version="v1", puzzle_id="p1")
    puzzle_item = create_training_item(
        db,
        source_type="puzzle",
        source_ref=puzzle_training_ref("v1", "p1"),
        skill="mate_in_one",
        operation="execute",
    )
    submit_training_move(
        db,
        "fixture-attempt",
        event_id="terminal",
        move="c5c8",
        item_id=puzzle_item,
        subject="learner",
    )
    return db


def test_wal_online_backup_and_restore_preserve_all_history(tmp_path):
    source = tmp_path / "live.sqlite"
    db = populated_wal(source)
    assert Path(str(source) + "-wal").stat().st_size > 0
    tables = (
        "games",
        "positions",
        "detector_runs",
        "detector_facts",
        "mapping_runs",
        "evidence_mappings",
        "evidence_review_events",
        "training_items",
        "training_attempts",
        "puzzle_sessions",
        "puzzle_session_events",
        "training_completions",
    )
    before = {
        name: [tuple(row) for row in db.connection.execute(f"SELECT * FROM {name}")]
        for name in tables
    }
    source_version = db.connection.execute("PRAGMA user_version").fetchone()[0]
    backup = tmp_path / "backup.sqlite"
    restored = tmp_path / "restored.sqlite"
    assert backup_database(source, backup, project_root=tmp_path) == backup
    backup_bytes = backup.read_bytes()
    assert restore_database(backup, restored, project_root=tmp_path) == restored
    assert backup.read_bytes() == backup_bytes
    assert not Path(str(backup) + "-wal").exists()
    assert not Path(str(backup) + "-shm").exists()
    for path in (backup, restored):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        with sqlite3.connect(path) as copy:
            assert copy.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert copy.execute("PRAGMA foreign_key_check").fetchall() == []
            assert copy.execute("PRAGMA user_version").fetchone()[0] == source_version
            assert {
                name: copy.execute(f"SELECT * FROM {name}").fetchall() for name in tables
            } == before
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == source_version
    assert [tuple(row) for row in db.connection.execute("SELECT * FROM games")] == before["games"]
    db.close()


def test_cli_backup_and_restore_do_not_initialize_or_upgrade_source(tmp_path):
    source = tmp_path / "legacy.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE old_data(value TEXT)")
        db.execute("INSERT INTO old_data VALUES ('fixture')")
        db.execute("PRAGMA user_version=1")
    backup = tmp_path / "backup.sqlite"
    restored = tmp_path / "restored.sqlite"
    sentinel = tmp_path / "must-not-be-created.sqlite"

    def run(command, source_path, target_path):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "chess_coach.cli",
                "--db",
                str(sentinel),
                command,
                str(source_path),
                str(target_path),
                "--project-root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert json.loads(result.stdout) == {"status": "verified"}
        assert "fixture" not in result.stdout + result.stderr

    run("backup-db", source, backup)
    run("restore-db", backup, restored)
    assert not sentinel.exists()
    for path in (source, backup, restored):
        with sqlite3.connect(path) as db:
            assert db.execute("PRAGMA user_version").fetchone()[0] == 1
            assert db.execute("SELECT value FROM old_data").fetchone()[0] == "fixture"


@pytest.mark.parametrize("operation", [backup_database, restore_database])
def test_existing_destination_is_not_modified(tmp_path, operation):
    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    target = tmp_path / "existing.sqlite"
    target.write_bytes(b"existing-data")
    with pytest.raises(FileExistsError, match="already exists"):
        operation(source, target, project_root=tmp_path)
    assert target.read_bytes() == b"existing-data"
