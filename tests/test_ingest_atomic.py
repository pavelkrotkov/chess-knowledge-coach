from __future__ import annotations

import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn

PGN = """[Event "Test"]
[Site "https://lichess.org/abc12345"]
[GameId "abc12345"]
[White "A"]
[Black "B"]
[Result "1-0"]

1. e4 e5 2. Nf3 1-0
"""


def database() -> Database:
    db = Database(":memory:")
    db.initialize()
    return db


def test_identical_replay_counts_only_new_records_and_preserves_raw_pgn() -> None:
    db = database()
    assert ingest_pgn(db, PGN, source="lichess", raw_pgn_override=PGN) == {
        "games": 1,
        "positions": 3,
    }
    before = [tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")]
    assert ingest_pgn(db, PGN, source="lichess", raw_pgn_override=PGN) == {
        "games": 0,
        "positions": 0,
    }
    assert db.connection.execute("SELECT pgn, source_id FROM games").fetchone()[:] == (
        PGN,
        "abc12345",
    )
    assert [
        tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")
    ] == before


def test_conflicting_stable_id_does_not_change_original() -> None:
    db = database()
    ingest_pgn(db, PGN, source="lichess", raw_pgn_override=PGN)
    before = [tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")]
    changed = PGN.replace("2. Nf3", "2. Bc4")
    with pytest.raises(ValueError, match="conflicting PGN"):
        ingest_pgn(db, changed, source="lichess", raw_pgn_override=changed)
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == PGN
    assert [
        tuple(row) for row in db.connection.execute("SELECT * FROM positions ORDER BY ply")
    ] == before


def test_bad_later_game_rolls_back_whole_import() -> None:
    db = database()
    valid = PGN.replace("abc12345", "abc12346")
    invalid = PGN.replace("2. Nf3", "2. Ke3")
    with pytest.raises(ValueError, match="invalid PGN"):
        ingest_pgn(db, valid + "\n" + invalid, source="lichess")
    assert not db.connection.in_transaction
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('later', 'A', 'B', '*')"
    )
    db.connection.commit()
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0
