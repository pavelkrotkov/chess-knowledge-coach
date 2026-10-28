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


def test_racing_destination_is_not_overwritten(tmp_path, monkeypatch):
    from chess_coach import recovery

    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    target = tmp_path / "race.sqlite"
    original = recovery.copy_database

    def race(source_path, temporary):
        original(source_path, temporary)
        target.write_bytes(b"other-writer")

    monkeypatch.setattr(recovery, "copy_database", race)
    with pytest.raises(FileExistsError, match="already exists"):
        backup_database(source, target, project_root=tmp_path)
    assert target.read_bytes() == b"other-writer"
    assert not list(tmp_path.glob(".chess-recovery-*"))


@pytest.mark.parametrize("operation", [backup_database, restore_database])
def test_corrupt_source_or_foreign_key_violation_fails_without_output(tmp_path, operation):
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"SQLite format 3" + bytes([0]) + b"damaged")
    before = corrupt.read_bytes()
    target = tmp_path / "backup.sqlite"
    with pytest.raises((sqlite3.DatabaseError, ValueError)):
        operation(corrupt, target, project_root=tmp_path)
    assert not target.exists() and corrupt.read_bytes() == before
    source = tmp_path / "invalid-fk.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
        db.execute("CREATE TABLE child(parent_id INTEGER REFERENCES parent(id))")
        db.execute("INSERT INTO child VALUES (9)")
    with pytest.raises(ValueError, match="foreign key"):
        operation(source, target, project_root=tmp_path)
    assert not target.exists()
    assert not list(tmp_path.glob(".chess-recovery-*"))


def test_injected_failure_cleans_temporary_file_and_preserves_source(tmp_path, monkeypatch):
    from chess_coach import recovery

    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
        db.execute("INSERT INTO sample VALUES (1)")
    before = source.read_bytes()
    target = tmp_path / "backup.sqlite"

    def fail(*args):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(recovery, "copy_database", fail)
    with pytest.raises(RuntimeError, match="injected"):
        backup_database(source, target, project_root=tmp_path)
    assert source.read_bytes() == before and not target.exists()
    assert not list(tmp_path.glob(".chess-recovery-*"))


def test_paths_must_be_inside_the_explicit_project_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    inside = root / "source.sqlite"
    with sqlite3.connect(inside) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    with pytest.raises(ValueError, match="within"):
        backup_database(inside, tmp_path / "outside.sqlite", project_root=root)
    outside = tmp_path / "outside.sqlite"
    with sqlite3.connect(outside) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    with pytest.raises(ValueError, match="within"):
        restore_database(outside, root / "restored.sqlite", project_root=root)


def test_publication_failure_removes_only_new_output(tmp_path, monkeypatch):
    from chess_coach import recovery

    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    before = source.read_bytes()
    target = tmp_path / "backup.sqlite"
    original = recovery.os.fsync

    def fail_directory(fd):
        if stat.S_ISDIR(recovery.os.fstat(fd).st_mode):
            raise OSError("injected directory sync failure")
        original(fd)

    monkeypatch.setattr(recovery.os, "fsync", fail_directory)
    with pytest.raises(OSError, match="injected"):
        backup_database(source, target, project_root=tmp_path)
    assert not target.exists() and source.read_bytes() == before
    assert not list(tmp_path.glob(".chess-recovery-*"))


def test_wal_backup_excludes_uncommitted_write_without_committing_source(tmp_path):
    source = tmp_path / "live.sqlite"
    db = populated_wal(source)
    before = db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    db.connection.execute(
        "INSERT INTO games(pgn,white,black,result) VALUES ('pending','A','B','1-0')"
    )
    assert db.connection.in_transaction
    target = tmp_path / "backup.sqlite"
    backup_database(source, target, project_root=tmp_path)
    assert db.connection.in_transaction
    with sqlite3.connect(target) as copy:
        assert copy.execute("SELECT COUNT(*) FROM games").fetchone()[0] == before
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == before + 1
    db.connection.rollback()
    db.close()


def test_temporary_backup_file_is_owner_only_before_copy(tmp_path, monkeypatch):
    from chess_coach import recovery

    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    target = tmp_path / "backup.sqlite"
    original = recovery.copy_database
    modes = []

    def inspect(source_path, temporary):
        modes.append(stat.S_IMODE(temporary.stat().st_mode))
        original(source_path, temporary)

    monkeypatch.setattr(recovery, "copy_database", inspect)
    backup_database(source, target, project_root=tmp_path)
    assert modes == [0o600]
    assert not list(tmp_path.glob(".chess-recovery-*"))


def test_restore_rejects_wal_mode_source_without_creating_sidecars(tmp_path):
    source = tmp_path / "wal-source.sqlite"
    db = sqlite3.connect(source)
    assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    db.execute("CREATE TABLE sample(id INTEGER)")
    db.commit()
    db.close()
    before = source.read_bytes()
    assert before[18:20] == bytes([2, 2])
    assert not Path(str(source) + "-wal").exists()
    assert not Path(str(source) + "-shm").exists()
    target = tmp_path / "restore.sqlite"
    with pytest.raises(ValueError, match="standalone backup"):
        restore_database(source, target, project_root=tmp_path)
    assert source.read_bytes() == before
    assert not Path(str(source) + "-wal").exists()
    assert not Path(str(source) + "-shm").exists()
    assert not target.exists()


@pytest.mark.parametrize("operation", [backup_database, restore_database])
@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_existing_sqlite_companion_blocks_publication(tmp_path, operation, suffix):
    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    target = tmp_path / "restored.sqlite"
    companion = Path(str(target) + suffix)
    companion.write_bytes(b"preserve-existing-companion")
    with pytest.raises(FileExistsError, match="companion"):
        operation(source, target, project_root=tmp_path)
    assert companion.read_bytes() == b"preserve-existing-companion"
    assert not target.exists()
    assert not list(tmp_path.glob(".chess-recovery-*"))


def test_hot_rollback_journal_blocks_restore_without_altering_artifacts(tmp_path):
    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE safe(value TEXT)")
        db.execute("INSERT INTO safe VALUES ('backup-data')")
    target = tmp_path / "restore.sqlite"
    script = """import os, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
db.execute('PRAGMA journal_mode=DELETE')
db.execute('PRAGMA cache_size=1')
db.execute('CREATE TABLE previous(data BLOB)')
db.executemany('INSERT INTO previous VALUES (?)', [(bytes(4000),)] * 100)
db.commit()
db.execute('BEGIN IMMEDIATE')
db.execute('UPDATE previous SET data=randomblob(4000)')
os._exit(0)
"""
    subprocess.run([sys.executable, "-c", script, str(target)], check=True)
    journal = Path(str(target) + "-journal")
    original = journal.read_bytes()
    assert original[:8] == bytes.fromhex("d9d505f920a163d7")
    target.unlink()  # Remove only the synthetic crashed fixture's main file.
    before = source.read_bytes()
    with pytest.raises(FileExistsError, match="companion"):
        restore_database(source, target, project_root=tmp_path)
    assert journal.read_bytes() == original and source.read_bytes() == before
    assert not target.exists()


@pytest.mark.parametrize("phase", ["before-link", "after-link"])
def test_companion_created_during_publication_fails_without_removing_it(
    tmp_path, monkeypatch, phase
):
    from chess_coach import recovery

    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    target = tmp_path / "new.sqlite"
    companion = Path(str(target) + "-journal")
    original_copy = recovery.copy_database
    original_link = recovery.os.link

    def racing_copy(source_path, temporary):
        original_copy(source_path, temporary)
        companion.write_bytes(b"concurrent journal")

    def racing_link(source_path, destination_path):
        original_link(source_path, destination_path)
        companion.write_bytes(b"concurrent journal")

    if phase == "before-link":
        monkeypatch.setattr(recovery, "copy_database", racing_copy)
    else:
        monkeypatch.setattr(recovery.os, "link", racing_link)
    with pytest.raises(FileExistsError, match="companion"):
        restore_database(source, target, project_root=tmp_path)
    assert companion.read_bytes() == b"concurrent journal"
    assert not target.exists()
    assert not list(tmp_path.glob(".chess-recovery-*"))


def test_dangling_sqlite_companion_symlink_is_not_overwritten(tmp_path):
    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(id INTEGER)")
    target = tmp_path / "new.sqlite"
    companion = Path(str(target) + "-wal")
    companion.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError, match="companion"):
        backup_database(source, target, project_root=tmp_path)
    assert companion.is_symlink() and not target.exists()
