import json

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.structures import extract_game_episodes

PGN = """[Event "Structure"]
[White "A"]
[Black "B"]
[Result "*"]

1. a3 a6 2. b3 b6 *
"""


def test_structure_episodes_are_versioned_and_repeatable() -> None:
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    game_id = db.connection.execute("SELECT id FROM games").fetchone()[0]

    count = extract_game_episodes(db, game_id, detector_version="test-1")
    again = extract_game_episodes(db, game_id, detector_version="test-1")

    assert count == again
    rows = db.connection.execute(
        "SELECT start_ply, end_ply, features_json, structure_json, confidence, detector_version "
        "FROM structure_episodes ORDER BY start_ply"
    ).fetchall()
    assert rows
    assert rows[0][0] == 1
    assert rows[-1][1] == 4
    assert "isolated_pawns" in json.loads(rows[0][2])
    assert isinstance(json.loads(rows[0][3]), list)
    assert rows[0][4] == 1.0
    assert rows[0][5] == "test-1"
