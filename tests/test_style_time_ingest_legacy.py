"""Legacy ingestion and fail-closed projection schema handling."""

import pytest

from chess_coach.db import SCHEMA, Database
from chess_coach.ingest import ingest_pgn

PGN = """[Event "Synthetic"]
[White "A"]
[Black "B"]
[UTCDate "2026.01.01"]
[UTCTime "12:00:00"]
[Result "*"]

1. e4 e5 *
"""


def objects(db):
    return list(
        db.connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name")
    )


@pytest.mark.parametrize("version", [0, 1, 27])
def test_uninitialized_legacy_ingest_does_not_create_or_migrate_projection(version):
    db = Database(":memory:")
    db.connection.executescript(SCHEMA)
    db.connection.execute(f"PRAGMA user_version={version}")
    before = objects(db)
    assert ingest_pgn(db, PGN) == {"games": 1, "positions": 2}
    assert ingest_pgn(db, PGN) == {"games": 0, "positions": 0}
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == version
    assert objects(db) == before
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 2
    db.close()


@pytest.mark.parametrize("version", [1, 27, 28, 29, 30, 31])
def test_foreign_or_incomplete_projection_fails_before_inserting(version):
    db = Database(":memory:")
    db.initialize()
    db.connection.execute("DROP INDEX idx_style_time_white")
    db.connection.execute(f"PRAGMA user_version={version}")
    db.connection.commit()
    before = objects(db)
    with pytest.raises(RuntimeError, match="projection"):
        ingest_pgn(db, PGN)
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == version
    assert objects(db) == before
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
    db.close()


def test_current_schema_requires_projection_and_future_schema_is_rejected():
    for version in (28, 29, 30, 31, 32):
        db = Database(":memory:")
        db.initialize()
        if version in (28, 29, 30, 31):
            for name in ("style_time_insert", "style_time_invalidate"):
                db.connection.execute(f"DROP TRIGGER {name}")
            db.connection.execute("DROP TABLE style_game_times")
        db.connection.execute(f"PRAGMA user_version={version}")
        db.connection.commit()
        before = objects(db)
        with pytest.raises(RuntimeError, match="projection"):
            ingest_pgn(db, PGN)
        assert objects(db) == before
        assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
        db.close()


@pytest.mark.parametrize("version", [28, 29, 30, 31])
def test_current_projection_is_populated_for_new_ingest(version):
    db = Database(":memory:")
    db.initialize()
    db.connection.execute(f"PRAGMA user_version={version}")
    assert ingest_pgn(db, PGN)["games"] == 1
    row = db.connection.execute(
        "SELECT status,version,started_at,white_identity,black_identity FROM style_game_times"
    ).fetchone()
    assert tuple(row) == ("current", "utc-game-start-v1", "2026-01-01T12:00:00+00:00", "a", "b")
    db.close()


def test_corrupt_current_projection_rejects_even_identical_replay():
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    db.connection.execute("DROP INDEX idx_style_time_white")
    db.connection.commit()
    with pytest.raises(RuntimeError, match="projection"):
        ingest_pgn(db, PGN)
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    db.close()
