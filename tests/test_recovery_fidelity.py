"""Recovery verifies logical fidelity before publishing a copy."""

import sqlite3
from pathlib import Path

from chess_coach.recovery import backup_database, restore_database


def test_typed_rows_hidden_rowids_and_without_rowid_preserved(tmp_path, monkeypatch):
    _row_size_preflight_checks()
    source = tmp_path / "source.sqlite"
    target = tmp_path / "copy.sqlite"
    restored = tmp_path / "restore.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
        db.execute("CREATE TABLE child(parent_id INTEGER REFERENCES parent(id))")
        db.execute("INSERT INTO parent VALUES(1)")
        db.execute("INSERT INTO child VALUES(1)")
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
    from chess_coach import recovery_fidelity

    observed = []
    original_preflight = recovery_fidelity.preflight

    def observe_preflight(connection, table, deadline, limit):
        observed.append((connection, table, limit))
        return original_preflight(connection, table, deadline, limit)

    with monkeypatch.context() as patch:
        patch.setattr(recovery_fidelity, "preflight", observe_preflight)
        backup_database(source, target, project_root=tmp_path)
        restore_database(target, restored, project_root=tmp_path)
    assert observed and len(observed) % 2 == 0
    for left, right in zip(observed[::2], observed[1::2], strict=True):
        assert left[0] is not right[0] and left[1:] == right[1:]
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
    _zstd_recovery_checks(tmp_path, source, monkeypatch)
    _offline_pair_checks(tmp_path, monkeypatch)


def _row_size_preflight_checks():
    import pytest

    from chess_coach.recovery_fidelity_budget import preflight

    class Deadline:
        def check(self):
            pass

    for encoding, factor, codec in (("UTF-8", 1, "utf-8"), ("UTF-16le", 2, "utf-16le")):
        connection = sqlite3.connect(":memory:")
        connection.execute(f"PRAGMA encoding={encoding!r}")
        connection.text_factory = bytes
        connection.execute("CREATE TABLE sample(a,b,c,d,e)")
        connection.execute("INSERT INTO sample VALUES(NULL,NULL,NULL,NULL,NULL)")
        text, blob = "Aé🙂", b"a\x00bc"
        connection.execute("INSERT INTO sample VALUES(?,?,?,?,?)", (text, blob, 42, 1.25, None))
        exact = 256 + 128 * 5 + len(text.encode(codec)) * factor + len(blob) + 8 + 8
        preflight(connection, b"sample", Deadline(), exact)
        with pytest.raises(ValueError, match="row exceeds supported limit"):
            preflight(connection, b"sample", Deadline(), exact - 1)
        connection.execute("CREATE TABLE empty(a)")
        preflight(connection, b"empty", Deadline(), 1)
        connection.close()

    connection = sqlite3.connect(":memory:")
    connection.text_factory = bytes
    fields = ",".join(f"c{i}" for i in range(512))
    connection.execute("CREATE TABLE wide(" + fields + ")")
    connection.execute("INSERT INTO wide DEFAULT VALUES")
    preflight(connection, b"wide", Deadline(), 256 + 128 * 512)
    connection.execute("CREATE TABLE many(value)")
    connection.executemany("INSERT INTO many VALUES(?)", ((i,) for i in range(1000)))
    started = []

    def interrupt_aggregate(sql):
        if sql.startswith('SELECT 1 FROM "many"'):
            started.append(True)

    connection.set_trace_callback(interrupt_aggregate)
    connection.set_progress_handler(lambda: int(bool(started)), 1)
    try:
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            preflight(connection, b"many", Deadline(), 4096)
    finally:
        connection.set_progress_handler(None, 0)
        connection.set_trace_callback(None)
    assert started

    class ExpiresAfterQuery:
        def __init__(self):
            self.calls = 0

        def check(self):
            self.calls += 1
            if self.calls == 3:
                raise TimeoutError("synthetic deadline")

    deadline = ExpiresAfterQuery()
    with pytest.raises(TimeoutError, match="synthetic deadline"):
        preflight(connection, b"many", deadline, 4096)
    assert deadline.calls == 3
    connection.close()


def _compressed_recovery_checks(tmp_path, source, monkeypatch):
    import hashlib
    import json
    import shutil
    import subprocess
    import sys

    import pytest

    from chess_coach import (
        recovery_gzip,
        recovery_gzip_capacity,
        recovery_gzip_execute,
        recovery_gzip_files,
        recovery_gzip_memory,
        recovery_gzip_single,
        recovery_gzip_snapshot,
        recovery_physical,
    )
    from chess_coach.recovery_gzip import compressed_recovery
    from chess_coach.recovery_gzip_restore import restore
    from chess_coach.recovery_gzip_single import restore_backup

    checks = []
    for module, name, label in (
        (recovery_gzip_snapshot, "verify_database", "source"),
        (recovery_gzip_execute, "verify_database", "composite"),
        (recovery_gzip_single, "verify_database", "standalone"),
        (recovery_gzip_single, "verify_metadata", "metadata"),
    ):
        original = getattr(module, name)

        def checked(connection, *args, _original=original, _label=label):
            assert connection.execute("PRAGMA temp_store").fetchone()[0] == 2
            checks.append(_label)
            return _original(connection, *args)

        monkeypatch.setattr(module, name, checked)
    original_fidelity = recovery_gzip_execute.verify_fidelity

    def fidelity_memory(reader, writer, deadline):
        assert reader.execute("PRAGMA temp_store").fetchone()[0] == 2
        assert writer.execute("PRAGMA temp_store").fetchone()[0] == 2
        checks.append("fidelity")
        return original_fidelity(reader, writer, deadline)

    monkeypatch.setattr(recovery_gzip_execute, "verify_fidelity", fidelity_memory)
    _gzip_resource_checks(tmp_path, source, monkeypatch)
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
    isolated = tmp_path / "archive-only"
    isolated.mkdir()
    retained = isolated / "retained.gz"
    retained_manifest = Path(str(retained) + ".manifest.json")
    shutil.copyfile(archive, retained)
    shutil.copyfile(manifest_path, retained_manifest)
    recovered = isolated / "recovered.sqlite"
    assert (
        restore_backup(retained, recovered, project_root=tmp_path, check_only=True)["status"]
        == "fits"
    )
    assert not recovered.exists()
    assert restore_backup(retained, recovered, project_root=tmp_path) == {"status": "verified"}
    assert hashlib.sha256(recovered.read_bytes()).hexdigest() == manifest["raw_sha256"]
    assert {"source", "composite", "standalone", "metadata", "fidelity"} <= set(checks)
    assert retained.read_bytes() == archive.read_bytes()
    unsupported = isolated / "unsupported.sqlite"

    def force_unsupported(_connection):
        raise ValueError("SQLite memory-only temporary storage unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(recovery_gzip_memory, "compile_mode", force_unsupported)
        with pytest.raises(ValueError, match="memory-only"):
            restore_backup(retained, unsupported, project_root=tmp_path)
        with pytest.raises(ValueError, match="memory-only"):
            compressed_recovery(
                source,
                isolated / "unsupported.gz",
                isolated / "unsupported-copy.sqlite",
                project_root=tmp_path,
            )
    assert not unsupported.exists() and not (isolated / "unsupported.gz").exists()
    assert not (isolated / "unsupported-copy.sqlite").exists()
    assert not list(tmp_path.glob(".chess-recovery-*"))
    with pytest.raises(FileExistsError):
        restore_backup(retained, recovered, project_root=tmp_path)
    bad_manifest = {**manifest, "version": "invalid"}
    retained_manifest.write_text(json.dumps(bad_manifest))
    with pytest.raises(ValueError, match="manifest invalid"):
        restore_backup(retained, isolated / "invalid.sqlite", project_root=tmp_path)
    assert not (isolated / "invalid.sqlite").exists()
    retained_manifest.write_text(
        json.dumps({**manifest, "user_version": manifest["user_version"] + 1})
    )
    with pytest.raises(ValueError, match="metadata differs"):
        restore_backup(retained, isolated / "mismatch.sqlite", project_root=tmp_path)
    assert not (isolated / "mismatch.sqlite").exists()
    retained_manifest.write_text(json.dumps(manifest))
    with monkeypatch.context() as patch:
        patch.setattr(recovery_gzip_capacity, "PROJECT_LIMIT", 1)
        assert (
            restore_backup(
                retained, isolated / "no-space.sqlite", project_root=tmp_path, check_only=True
            )["status"]
            == "insufficient"
        )
        with pytest.raises(ValueError, match="capacity unavailable"):
            restore_backup(retained, isolated / "no-space.sqlite", project_root=tmp_path)
    assert not (isolated / "no-space.sqlite").exists()
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
    Path(str(corrupted) + ".manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="archive verification"):
        restore_backup(corrupted, tmp_path / "bad-gzip.sqlite", project_root=tmp_path)
    assert not (tmp_path / "bad-gzip.sqlite").exists()
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


def _zstd_recovery_checks(tmp_path, source, monkeypatch):
    import hashlib
    import io
    import json
    import shutil
    import subprocess
    import time

    import pytest

    from chess_coach import recovery_gzip, recovery_gzip_capacity, recovery_physical
    from chess_coach.recovery_deadline import Deadline
    from chess_coach.recovery_gzip import compressed_recovery
    from chess_coach.recovery_gzip_single import restore_backup
    from chess_coach.recovery_zstd_process import transform

    # This disposable test database is distinct from the preserved original fixture.
    synthetic_source = tmp_path / "zstd-source.sqlite"
    shutil.copyfile(source, synthetic_source)
    archive = tmp_path / "backup.sqlite.zst"
    restored = tmp_path / "zstd-verified.sqlite"
    manifest_path = Path(str(archive) + ".manifest.json")
    report = compressed_recovery(
        synthetic_source, archive, restored, project_root=tmp_path, codec="zstd", check_only=True
    )
    assert report["status"] == "conditional"
    assert not archive.exists() and not restored.exists() and not manifest_path.exists()
    assert compressed_recovery(
        synthetic_source, archive, restored, project_root=tmp_path, codec="zstd"
    ) == {"status": "verified"}
    manifest = json.loads(manifest_path.read_text())
    assert manifest["version"] == "sqlite-zstd-recovery-v1"
    assert (manifest["codec"], manifest["compression_level"], manifest["threads"]) == ("zstd", 6, 1)
    assert manifest["checksum"] == "xxh64" and manifest["typed_fidelity"] == "ok"
    assert manifest["raw_sha256"] == hashlib.sha256(synthetic_source.read_bytes()).hexdigest()
    assert manifest["raw_sha256"] == hashlib.sha256(restored.read_bytes()).hexdigest()
    assert manifest["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    synthetic_source.unlink()
    assert not synthetic_source.exists()
    recovered = tmp_path / "zstd-standalone.sqlite"
    assert (
        restore_backup(archive, recovered, project_root=tmp_path, codec="zstd", check_only=True)[
            "status"
        ]
        == "fits"
    )
    assert restore_backup(archive, recovered, project_root=tmp_path, codec="zstd") == {
        "status": "verified"
    }
    assert hashlib.sha256(recovered.read_bytes()).hexdigest() == manifest["raw_sha256"]
    with sqlite3.connect(source) as original, sqlite3.connect(recovered) as result:
        original.text_factory = result.text_factory = bytes
        query = 'SELECT rowid,x,y,z FROM "odd""name" ORDER BY rowid'
        assert result.execute(query).fetchall() == original.execute(query).fetchall()
        result.text_factory = str
        assert result.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert result.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(ValueError, match="manifest invalid"):
        restore_backup(archive, tmp_path / "wrong-format.sqlite", project_root=tmp_path)
    with pytest.raises(ValueError, match="manifest invalid"):
        restore_backup(
            tmp_path / "backup.sqlite.gz",
            tmp_path / "wrong-zstd.sqlite",
            project_root=tmp_path,
            codec="zstd",
        )
    unchecked = subprocess.run(
        ["/usr/bin/zstd", "-q", "--no-check", "-c"],
        input=source.read_bytes(),
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout
    no_checksum = tmp_path / "no-checksum.zst"
    no_checksum.write_bytes(unchecked)
    Path(str(no_checksum) + ".manifest.json").write_text(
        json.dumps(
            {
                **manifest,
                "archive_bytes": len(unchecked),
                "archive_sha256": hashlib.sha256(unchecked).hexdigest(),
            }
        )
    )
    with pytest.raises(ValueError, match="checksum"):
        restore_backup(
            no_checksum, tmp_path / "no-checksum.sqlite", project_root=tmp_path, codec="zstd"
        )
    assert not (tmp_path / "no-checksum.sqlite").exists()
    existing = tmp_path / "zstd-existing.sqlite"
    existing.write_bytes(b"preserved")
    with pytest.raises(FileExistsError):
        restore_backup(archive, existing, project_root=tmp_path, codec="zstd")
    assert existing.read_bytes() == b"preserved"
    for name, data in (
        ("truncated", archive.read_bytes()[:-1]),
        (
            "corrupt",
            archive.read_bytes()[: len(archive.read_bytes()) // 2]
            + bytes([archive.read_bytes()[len(archive.read_bytes()) // 2] ^ 1])
            + archive.read_bytes()[len(archive.read_bytes()) // 2 + 1 :],
        ),
    ):
        damaged = tmp_path / (name + ".zst")
        damaged.write_bytes(data)
        Path(str(damaged) + ".manifest.json").write_text(
            json.dumps(
                {
                    **manifest,
                    "archive_bytes": len(data),
                    "archive_sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        )
        destination = tmp_path / (name + ".sqlite")
        with pytest.raises(ValueError):
            restore_backup(damaged, destination, project_root=tmp_path, codec="zstd")
        assert not destination.exists()
    with monkeypatch.context() as patch:
        patch.setattr(recovery_gzip_capacity, "PROJECT_LIMIT", 1)
        patch.setattr(recovery_physical, "PROJECT_LIMIT", 1)
        blocked = tmp_path / "zstd-no-space.zst"
        assert (
            compressed_recovery(
                source,
                blocked,
                tmp_path / "zstd-no-space.sqlite",
                project_root=tmp_path,
                codec="zstd",
                check_only=True,
            )["status"]
            == "insufficient"
        )
        with pytest.raises(ValueError, match="capacity unavailable"):
            compressed_recovery(
                source,
                blocked,
                tmp_path / "zstd-no-space.sqlite",
                project_root=tmp_path,
                codec="zstd",
            )
    assert not blocked.exists()
    original_plan = recovery_gzip.pinned_plan
    with monkeypatch.context() as patch:
        patch.setattr(
            recovery_gzip,
            "pinned_plan",
            lambda *args: {**original_plan(*args), "archive_limit_bytes": 1},
        )
        capped = tmp_path / "zstd-capped.zst"
        with pytest.raises(ValueError, match="output exceeds"):
            compressed_recovery(
                source, capped, tmp_path / "zstd-capped.sqlite", project_root=tmp_path, codec="zstd"
            )
    assert not capped.exists() and not (tmp_path / "zstd-capped.sqlite").exists()
    assert not Path(str(capped) + ".manifest.json").exists()
    from chess_coach import recovery_zstd_process

    processes = []
    popen = subprocess.Popen

    def start(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    class Guard:
        def check(self, *_args, **_kwargs):
            pass

    expired = Deadline()
    expired.end = time.monotonic() - 1
    with monkeypatch.context() as patch:
        patch.setattr(recovery_zstd_process.subprocess, "Popen", start)
        with pytest.raises(TimeoutError):
            transform(
                io.BytesIO(b"data"),
                io.BytesIO(),
                ["-q", "-c"],
                4,
                100,
                Guard(),
                expired,
                restoring=False,
            )
    assert processes and processes[0].poll() is not None
    assert not list(tmp_path.glob(".chess-recovery-*"))


def _gzip_resource_checks(tmp_path, source, monkeypatch):
    from types import SimpleNamespace

    import pytest

    from chess_coach import recovery_gzip_capacity, recovery_gzip_memory, recovery_physical
    from chess_coach.recovery_capacity import MIN_WORKING, RESERVE
    from chess_coach.recovery_deadline import Deadline
    from chess_coach.recovery_gzip import compressed_recovery

    class FileOnlyBuild:
        def execute(self, command):
            assert command == "PRAGMA compile_options"
            return [("TEMP_STORE=0",)]

    with pytest.raises(ValueError, match="memory-only"):
        recovery_gzip_memory.configure(FileOnlyBuild())

    class Result(list):
        def fetchone(self):
            return self[0]

    class RefusesMemory:
        def execute(self, command):
            if command == "PRAGMA compile_options":
                return [("TEMP_STORE=1",)]
            if command == "PRAGMA temp_store":
                return Result([(1,)])
            assert command == "PRAGMA temp_store=MEMORY"
            return Result([])

    class AlreadyMemory:
        def execute(self, command):
            if command == "PRAGMA compile_options":
                return [("TEMP_STORE=1",)]
            assert command == "PRAGMA temp_store"
            return Result([(2,)])

    with pytest.raises(ValueError, match="memory-only"):
        recovery_gzip_memory.configure(RefusesMemory())
    recovery_gzip_memory.configure(AlreadyMemory())
    invalid = tmp_path / "invalid-sqlite"
    invalid.write_bytes(b"not a SQLite database")
    with pytest.raises(ValueError, match="valid SQLite"):
        compressed_recovery(
            invalid,
            tmp_path / "invalid.gz",
            tmp_path / "invalid-copy",
            project_root=tmp_path,
            check_only=True,
        )
    size = 2 * 1024**3
    state = (1, 2, size, 3, 4)
    limit = size + MIN_WORKING + RESERVE + recovery_gzip_capacity.MANIFEST_ALLOWANCE + 4096
    target = tmp_path / "boundary.gz"
    with monkeypatch.context() as patch:
        patch.setattr(
            recovery_physical, "_file_state", lambda path: state if path == source else None
        )
        patch.setattr(recovery_physical, "allocated", lambda *_: 0)
        patch.setattr(recovery_gzip_capacity, "allocated", lambda *_: 0)
        patch.setattr(recovery_physical, "PROJECT_LIMIT", limit)
        patch.setattr(recovery_gzip_capacity, "PROJECT_LIMIT", limit)
        patch.setattr("shutil.disk_usage", lambda *_: SimpleNamespace(free=limit * 2))
        native = recovery_physical.physical(source, tmp_path, target, Deadline())
        fixed = recovery_physical.physical(
            source, tmp_path, target, Deadline(), working_bytes=MIN_WORKING
        )
        assert native["working_bytes"] == size // 10 and native["status"] == "insufficient"
        assert fixed["working_bytes"] == MIN_WORKING and fixed["status"] == "fits"
        report = compressed_recovery(
            source, target, tmp_path / "boundary.sqlite", project_root=tmp_path, check_only=True
        )
        assert report["working_bytes"] == MIN_WORKING and report["status"] == "conditional"
        assert report["archive_limit_bytes"] == 4096 and not target.exists()
        patch.setattr(recovery_gzip_capacity, "snapshot", lambda _: (size // 4096, 4096))
        pinned = recovery_gzip_capacity.pinned_plan(None, tmp_path, target, Deadline())
        later = recovery_gzip_capacity.restore_plan(size, tmp_path, target, Deadline())
        assert pinned["working_bytes"] == later["working_bytes"] == MIN_WORKING
        assert pinned["archive_limit_bytes"] == later["archive_limit_bytes"] == 4096
        calls = []

        def changed(path):
            if path != source:
                return None
            calls.append(True)
            return state if len(calls) == 1 else (1, 2, size, 4, 4)

        patch.setattr(recovery_physical, "_file_state", changed)
        report = compressed_recovery(
            source, target, tmp_path / "boundary.sqlite", project_root=tmp_path, check_only=True
        )
        assert report["status"] == "unavailable" and not target.exists()


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


def _offline_pair_checks(tmp_path, monkeypatch):
    """Exercise the CLI against generated SQLite and retained failure evidence."""
    import contextlib
    import io
    import json
    import os
    import signal
    import sys

    import pytest

    from chess_coach import cli, recovery_pair, recovery_pair_restore

    def setup(name):
        directory = tmp_path / name
        directory.mkdir()
        source = directory / "source.sqlite"
        connection = sqlite3.connect(source)
        connection.execute("CREATE TABLE sample(value TEXT)")
        connection.execute("INSERT INTO sample VALUES('synthetic')")
        connection.commit()
        connection.close()
        return directory, source, source.read_bytes()

    def arguments(directory, source):
        return [
            str(source),
            str(directory / "a.gz"),
            str(directory / "b.gz"),
            str(directory / "restored.sqlite"),
            "--project-root",
            str(tmp_path),
            "--acknowledge-source-unlink",
        ]

    def run(args):
        monkeypatch.setattr(sys, "argv", ["chess-coach", *args])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            cli.main()
        return json.loads(output.getvalue())

    def recover(directory):
        return run(
            [
                "restore-offline-gzip-pair",
                str(directory / "a.gz"),
                str(directory / "b.gz"),
                str(directory / "a.gz.pair.json"),
                str(directory / "manual.sqlite"),
                "--project-root",
                str(tmp_path),
            ]
        )

    directory, source, original = setup("offline-pair-success")
    assert run(["offline-gzip-pair", *arguments(directory, source)])["status"] == "verified"
    assert not source.exists()
    assert (directory / "restored.sqlite").read_bytes() == original
    metadata = json.loads((directory / "a.gz.pair.json").read_text())
    assert metadata["verified"] == "both_archives_match_sole_leased_source"
    assert "typed_fidelity" not in metadata and "restore_integrity" not in metadata
    assert recover(directory)["status"] == "verified"
    assert (directory / "manual.sqlite").read_bytes() == original
    assert (directory / "a.gz").exists() and (directory / "b.gz").exists()

    directory, source, original = setup("offline-pair-corrupt")
    prove = recovery_pair._prove_pair

    def truncate(lease, a, b, metadata, first, second, deadline):
        b.write_bytes(b.read_bytes()[:-1])
        return prove(lease, a, b, metadata, first, second, deadline)

    with monkeypatch.context() as patch:
        patch.setattr(recovery_pair, "_prove_pair", truncate)
        with pytest.raises(ValueError, match="archive"):
            run(["offline-gzip-pair", *arguments(directory, source)])
    assert source.read_bytes() == original

    directory, source, original = setup("offline-pair-capacity")
    check_space = recovery_pair.require_space

    def no_reclaim(root, target, deadline, remaining=0, credit=0):
        if credit:
            raise ValueError("offline recovery capacity unavailable")
        return check_space(root, target, deadline, remaining, credit)

    with monkeypatch.context() as patch:
        patch.setattr(recovery_pair, "require_space", no_reclaim)
        with pytest.raises(ValueError, match="capacity"):
            run(["offline-gzip-pair", *arguments(directory, source)])
    assert source.read_bytes() == original
    assert (directory / "a.gz").exists() and (directory / "b.gz").exists()

    directory, source, original = setup("offline-pair-break")
    original_check = recovery_pair.Lease.check

    def break_lease(lease):
        os.kill(os.getpid(), signal.SIGIO)
        original_check(lease)

    with monkeypatch.context() as patch:
        patch.setattr(recovery_pair.Lease, "check", break_lease)
        with pytest.raises(ValueError, match="lease broken"):
            run(["offline-gzip-pair", *arguments(directory, source)])
    assert source.read_bytes() == original

    directory, source, original = setup("offline-pair-post-unlink")

    compared = []
    original_compare = recovery_pair_restore.compare

    def observe_compare(*args, **kwargs):
        result = original_compare(*args, **kwargs)
        compared.append(True)
        return result

    def interrupt_after_restore(path, _deadline):
        assert compared == [True]
        assert path.read_bytes() == original
        raise KeyboardInterrupt("synthetic post-unlink interruption")

    with monkeypatch.context() as patch:
        patch.setattr(recovery_pair_restore, "compare", observe_compare)
        patch.setattr(recovery_pair_restore, "verify_standalone", interrupt_after_restore)
        with pytest.raises(RuntimeError, match="source unlinked") as error:
            run(["offline-gzip-pair", *arguments(directory, source)])
    assert isinstance(error.value.__cause__, KeyboardInterrupt)
    assert not source.exists()
    assert not (directory / "restored.sqlite").exists()
    assert not list(directory.glob(".chess-recovery-*"))
    assert (directory / "a.gz").exists() and (directory / "b.gz").exists()
    assert (directory / "a.gz.pair.json").exists()
    assert recover(directory)["status"] == "verified"
    assert (directory / "manual.sqlite").read_bytes() == original
