"""Prove the backup API uses the pinned source snapshot under a WAL writer."""

import sqlite3


def test_pinned_wal_source_snapshot_survives_concurrent_commit(tmp_path):
    path = tmp_path / "source.sqlite"
    setup = sqlite3.connect(path)
    assert setup.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    setup.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
    setup.executemany("INSERT INTO sample VALUES (?, ?)", [(i, "a" * 2000) for i in range(1, 301)])
    setup.commit()
    reader = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    destination = sqlite3.connect(tmp_path / "copy.sqlite")
    writer = sqlite3.connect(path, timeout=1)
    try:
        reader.execute("BEGIN")
        assert reader.execute("SELECT value FROM sample WHERE id=1").fetchone()[0] == "a" * 2000
        commits = []

        def concurrent_write(status, remaining, total):
            if not commits:
                assert remaining > 0
                writer.execute("UPDATE sample SET value=? WHERE id=1", ("changed",))
                writer.commit()
                commits.append(True)

        reader.backup(destination, pages=1, progress=concurrent_write)
        assert commits == [True]
        assert reader.execute("SELECT value FROM sample WHERE id=1").fetchone()[0] == "a" * 2000
        assert (
            destination.execute("SELECT value FROM sample WHERE id=1").fetchone()[0] == "a" * 2000
        )
        assert writer.execute("SELECT value FROM sample WHERE id=1").fetchone()[0] == "changed"
    finally:
        reader.close()
        destination.close()
        writer.close()
        setup.close()
