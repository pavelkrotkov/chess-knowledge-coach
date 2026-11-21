"""Recovery verifies logical fidelity before publishing a copy."""

import sqlite3
from pathlib import Path

from chess_coach.recovery import backup_database, restore_database


def test_typed_rows_hidden_rowids_and_without_rowid_preserved(tmp_path, monkeypatch):
    source = tmp_path / "source.sqlite"
    target = tmp_path / "copy.sqlite"
    restored = tmp_path / "restore.sqlite"
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE "odd""name"(x, y, z)')
        db.execute('INSERT INTO "odd""name"(rowid,x,y,z) VALUES(-7, NULL, ?, ?)', (1, 1.25))
        db.execute('INSERT INTO "odd""name"(rowid,x,y,z) VALUES(9, ?, ?, ?)', ("same", b"same", 1))
        db.execute('INSERT INTO "odd""name"(rowid,x,y,z) VALUES(11, ?, ?, ?)', ("same", b"same", 1))
        db.execute(
            'INSERT INTO "odd""name"(rowid,x,y,z) VALUES(12, CAST(? AS TEXT), ?, NULL)',
            (bytes([128, 255]), bytes([128, 255])),
        )
        db.execute(
            "CREATE TABLE wr (a TEXT COLLATE NOCASE, b INTEGER, val BLOB, PRIMARY KEY(a DESC,b ASC)) WITHOUT ROWID"
        )
        db.executemany("INSERT INTO wr VALUES(?,?,?)", [("Beta", 1, b"a"), ("alpha", 3, b"b")])
        db.execute("CREATE TABLE aliases (id INTEGER PRIMARY KEY, value)")
        db.execute("INSERT INTO aliases VALUES(-5, ?)", ("x",))
    backup_database(source, target, project_root=tmp_path)
    restore_database(target, restored, project_root=tmp_path)
    with sqlite3.connect(source) as left, sqlite3.connect(restored) as right:
        left.text_factory = right.text_factory = bytes
        for query in (
            'SELECT rowid,* FROM "odd""name" ORDER BY rowid',
            "SELECT * FROM wr ORDER BY a COLLATE NOCASE DESC,b ASC",
            "SELECT rowid,* FROM aliases ORDER BY rowid",
        ):
            assert left.execute(query).fetchall() == right.execute(query).fetchall()
    db.close()
    left.close()
    right.close()
    _compressed_recovery_checks(tmp_path, source, monkeypatch)


def _compressed_recovery_checks(tmp_path, source, monkeypatch):
    import hashlib
    import json
    import subprocess
    import sys

    import pytest

    from chess_coach import (
        recovery_gzip,
        recovery_gzip_capacity,
        recovery_gzip_execute,
        recovery_gzip_files,
        recovery_physical,
    )
    from chess_coach.recovery_gzip import compressed_recovery
    from chess_coach.recovery_gzip_restore import restore

    archive = tmp_path / "backup.sqlite.gz"
    restored = tmp_path / "gzip-restored.sqlite"
    manifest_path = tmp_path / "backup.sqlite.gz.manifest.json"
    estimate = compressed_recovery(
        source, archive, restored, project_root=tmp_path, check_only=True
    )
    assert estimate["status"] == "conditional" and estimate["archive_limit_bytes"] > 0
    assert not archive.exists() and not restored.exists() and not manifest_path.exists()
    real_verify = recovery_gzip_execute._verify
    attempts = []

    def check_locked(reader, path, deadline):
        code = (
            "import sqlite3,sys; c=sqlite3.connect(sys.argv[1], timeout=0.1); "
            "c.execute('INSERT INTO aliases VALUES(100, 1)'); c.commit()"
        )
        result = subprocess.run([sys.executable, "-c", code, str(source)], capture_output=True)
        assert result.returncode != 0 and b"locked" in result.stderr
        attempts.append(True)
        return real_verify(reader, path, deadline)

    with monkeypatch.context() as patch:
        patch.setattr(recovery_gzip_execute, "_verify", check_locked)
        assert compressed_recovery(source, archive, restored, project_root=tmp_path) == {
            "status": "verified"
        }
    assert attempts == [True]
    manifest = json.loads(manifest_path.read_text())
    assert manifest["typed_fidelity"] == manifest["source_integrity"] == "ok"
    assert manifest["raw_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest["raw_sha256"] == hashlib.sha256(restored.read_bytes()).hexdigest()
    assert manifest["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert archive.stat().st_mode & 0o777 == 0o600
    assert restored.stat().st_mode & 0o777 == 0o600
    assert manifest_path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        compressed_recovery(source, archive, restored, project_root=tmp_path)
    corrupted = tmp_path / "corrupt.sqlite.gz"
    data = bytearray(archive.read_bytes())
    data[len(data) // 2] ^= 1
    corrupted.write_bytes(data)

    class NoopGuard:
        def check(self, *_args, **_kwargs):
            pass

    from chess_coach.recovery_deadline import Deadline

    with pytest.raises(ValueError, match="archive verification"):
        restore(corrupted, tmp_path / "corrupt-restored.sqlite", manifest, NoopGuard(), Deadline())
    assert not (tmp_path / "corrupt-restored.sqlite").exists()
    no_space = tmp_path / "no-space.sqlite.gz"
    with monkeypatch.context() as patch:
        patch.setattr(recovery_gzip_capacity, "PROJECT_LIMIT", 1)
        patch.setattr(recovery_physical, "PROJECT_LIMIT", 1)
        assert (
            compressed_recovery(
                source,
                no_space,
                tmp_path / "no-space.sqlite",
                project_root=tmp_path,
                check_only=True,
            )["status"]
            == "insufficient"
        )
        with pytest.raises(ValueError, match="capacity unavailable"):
            compressed_recovery(
                source, no_space, tmp_path / "no-space.sqlite", project_root=tmp_path
            )
    assert not no_space.exists()
    capped = tmp_path / "capped.sqlite.gz"
    capped_restore = tmp_path / "capped.sqlite"
    original_plan = recovery_gzip.pinned_plan
    with monkeypatch.context() as patch:

        def tiny_cap(*args):
            return {**original_plan(*args), "archive_limit_bytes": 1}

        patch.setattr(recovery_gzip, "pinned_plan", tiny_cap)
        with pytest.raises(ValueError, match="compressed backup exceeded"):
            compressed_recovery(source, capped, capped_restore, project_root=tmp_path)
    assert not capped.exists() and not capped_restore.exists()
    assert not Path(str(capped) + ".manifest.json").exists()
    assert not list(tmp_path.glob(".chess-recovery-*"))
    partial = tmp_path / "partial.sqlite.gz"
    partial_restore = tmp_path / "partial.sqlite"
    real_publish = recovery_gzip_files._publish
    calls = []

    def interrupted_publish(staged, target):
        calls.append(True)
        if len(calls) == 3:
            raise OSError("fixture publication failure")
        return real_publish(staged, target)

    with monkeypatch.context() as patch:
        patch.setattr(recovery_gzip_files, "_publish", interrupted_publish)
        with pytest.raises(OSError, match="publication failure"):
            compressed_recovery(source, partial, partial_restore, project_root=tmp_path)
    assert not partial.exists() and not partial_restore.exists()
    assert not Path(str(partial) + ".manifest.json").exists()
    assert not list(tmp_path.glob(".chess-recovery-*"))
    wal = tmp_path / "wal.sqlite"
    with sqlite3.connect(wal) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        conn.execute("CREATE TABLE t(value)")
    conn.close()
    with pytest.raises(ValueError, match="standalone"):
        compressed_recovery(
            wal, tmp_path / "wal.gz", tmp_path / "wal-restored", project_root=tmp_path
        )


def test_committed_wal_writer_during_real_backup_keeps_pinned_snapshot(tmp_path, monkeypatch):
    from chess_coach import recovery_deadline

    source = tmp_path / "source.sqlite"
    target = tmp_path / "copy.sqlite"
    setup = sqlite3.connect(source)
    assert setup.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    setup.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, value TEXT)")
    setup.executemany("INSERT INTO items VALUES (?, ?)", [(i, "a" * 2000) for i in range(1, 601)])
    setup.commit()
    writer = sqlite3.connect(source, timeout=1)
    calls = []
    original = recovery_deadline.Deadline.backup_progress

    def write_once(deadline, status, remaining, total):
        original(deadline, status, remaining, total)
        if not calls:
            assert remaining > 0
            writer.execute("UPDATE items SET value='later' WHERE id=1")
            writer.commit()
            calls.append(True)

    monkeypatch.setattr(recovery_deadline.Deadline, "backup_progress", write_once)
    try:
        backup_database(source, target, project_root=tmp_path)
        assert calls == [True]
        with sqlite3.connect(target) as copy:
            assert copy.execute("SELECT value FROM items WHERE id=1").fetchone()[0] == "a" * 2000
        assert writer.execute("SELECT value FROM items WHERE id=1").fetchone()[0] == "later"
    finally:
        writer.close()
        setup.close()
