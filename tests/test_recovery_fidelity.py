"""Recovery verifies logical fidelity before publishing a copy."""

import sqlite3

from chess_coach.recovery import backup_database, restore_database


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
