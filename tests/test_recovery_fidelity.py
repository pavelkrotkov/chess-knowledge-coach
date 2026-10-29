"""Recovery verifies logical fidelity before publishing a copy."""

import sqlite3

import pytest

from chess_coach.recovery import backup_database, restore_database


def simple_source(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT)")
        db.execute("INSERT INTO items(value) VALUES (?)", ("private-fixture",))
        db.execute("PRAGMA user_version=7")
        db.execute("PRAGMA application_id=123")


@pytest.mark.parametrize("operation", [backup_database, restore_database])
@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE items SET value='changed' WHERE id=1",
        "UPDATE items SET id=42 WHERE id=1",
        "UPDATE sqlite_sequence SET seq=50 WHERE name='items'",
        "CREATE TABLE extra (id INTEGER)",
        "PRAGMA user_version=8",
        "PRAGMA application_id=456",
    ],
)
def test_structurally_valid_difference_is_never_published(
    tmp_path, monkeypatch, operation, mutation
):
    from chess_coach import recovery_copy

    source = tmp_path / "source.sqlite"
    target = tmp_path / "copy.sqlite"
    simple_source(source)
    original = recovery_copy.verify_fidelity

    def alter(reader, writer, deadline):
        writer.execute(mutation)
        writer.commit()
        assert writer.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        original(reader, writer, deadline)

    monkeypatch.setattr(recovery_copy, "verify_fidelity", alter)
    with pytest.raises(ValueError, match="logical fidelity") as error:
        operation(source, target, project_root=tmp_path)
    assert "private-fixture" not in str(error.value)
    assert not target.exists() and not list(tmp_path.glob(".chess-recovery-*"))
    with sqlite3.connect(source) as db:
        assert db.execute("SELECT value FROM items").fetchone()[0] == "private-fixture"


def test_typed_rows_hidden_rowids_and_without_rowid_preserved(tmp_path):
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


def test_unavailable_or_unsupported_schema_fails_closed(tmp_path):
    source = tmp_path / "source.sqlite"
    target = tmp_path / "copy.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE shadowed(rowid TEXT, _rowid_ TEXT, oid TEXT)")
    with pytest.raises(ValueError, match="logical fidelity"):
        backup_database(source, target, project_root=tmp_path)
    assert not target.exists()


def test_size_limit_and_deadline_leave_no_published_copy(tmp_path, monkeypatch):
    from chess_coach import recovery_deadline, recovery_fidelity

    source = tmp_path / "source.sqlite"
    target = tmp_path / "copy.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE large(value BLOB)")
        db.execute("INSERT INTO large VALUES (?)", (b"x" * 3000,))
    with monkeypatch.context() as patch:
        patch.setattr(recovery_fidelity, "MAX_RECORD_BYTES", 1024)
        with pytest.raises(ValueError, match="logical fidelity"):
            backup_database(source, target, project_root=tmp_path)
    assert not target.exists()
    monkeypatch.setattr(recovery_deadline, "SECONDS", 0)
    with pytest.raises(TimeoutError, match="time limit"):
        backup_database(source, target, project_root=tmp_path)
    assert not target.exists() and not list(tmp_path.glob(".chess-recovery-*"))


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


def test_changes_to_sqlite_storage_types_are_detected(tmp_path, monkeypatch):
    from chess_coach import recovery_copy

    source, target = tmp_path / "source.sqlite", tmp_path / "copy.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(value)")
        db.execute("INSERT INTO sample VALUES(1)")
    original = recovery_copy.verify_fidelity

    def change_type(reader, writer, deadline):
        writer.execute("UPDATE sample SET value=1.0")
        writer.commit()
        original(reader, writer, deadline)

    monkeypatch.setattr(recovery_copy, "verify_fidelity", change_type)
    with pytest.raises(ValueError, match="logical fidelity"):
        backup_database(source, target, project_root=tmp_path)
    assert not target.exists()


def test_comparison_deadline_leaves_no_output(tmp_path, monkeypatch):
    import time

    from chess_coach import recovery_copy

    source, target = tmp_path / "source.sqlite", tmp_path / "copy.sqlite"
    simple_source(source)
    original = recovery_copy.verify_fidelity

    def expire(reader, writer, deadline):
        deadline.end = time.monotonic() - 1
        original(reader, writer, deadline)

    monkeypatch.setattr(recovery_copy, "verify_fidelity", expire)
    with pytest.raises(TimeoutError, match="time limit"):
        backup_database(source, target, project_root=tmp_path)
    assert not target.exists() and not list(tmp_path.glob(".chess-recovery-*"))


def test_virtual_table_is_rejected_without_publish(tmp_path):
    source, target = tmp_path / "source.sqlite", tmp_path / "copy.sqlite"
    with sqlite3.connect(source) as db:
        try:
            db.execute("CREATE VIRTUAL TABLE indexed USING fts5(content)")
        except sqlite3.OperationalError:
            pytest.skip("SQLite build lacks FTS5")
    with pytest.raises(ValueError, match="logical fidelity"):
        backup_database(source, target, project_root=tmp_path)
    assert not target.exists()
