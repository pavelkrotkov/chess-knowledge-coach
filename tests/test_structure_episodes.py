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


def test_episode_boundaries_and_versions_preserve_provenance() -> None:
    import chess

    from chess_coach.structures import extract_features

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    game_id = db.connection.execute("SELECT id FROM games").fetchone()[0]
    fen = chess.Board().fen()
    db.connection.execute("UPDATE positions SET fen = ? WHERE game_id = ?", (fen, game_id))
    db.connection.execute("DELETE FROM positions WHERE game_id = ? AND ply = 2", (game_id,))
    db.connection.commit()

    assert extract_game_episodes(db, game_id, detector_version="v1") == 2
    columns = "start_ply, end_ply, features_json, structure_json, confidence, detector_version"
    rows = db.connection.execute(
        f"SELECT {columns} FROM structure_episodes WHERE game_id = ? ORDER BY start_ply",
        (game_id,),
    ).fetchall()
    assert [(row[0], row[1]) for row in rows] == [(1, 1), (3, 4)]
    assert all(json.loads(row[2]) == extract_features(chess.Board(fen)) for row in rows)
    assert all(json.loads(row[3]) == [] and row[4] == 1.0 and row[5] == "v1" for row in rows)
    first = [tuple(row) for row in rows]

    assert extract_game_episodes(db, game_id, detector_version="v2") == 2
    assert extract_game_episodes(db, game_id, detector_version="v1") == 2
    rows = db.connection.execute(
        f"SELECT {columns} FROM structure_episodes "
        "WHERE game_id = ? AND detector_version = ? ORDER BY start_ply",
        (game_id, "v1"),
    ).fetchall()
    assert [tuple(row) for row in rows] == first
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM structure_episodes WHERE game_id = ? AND detector_version = ?",
            (game_id, "v2"),
        ).fetchone()[0]
        == 2
    )
