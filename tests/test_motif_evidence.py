import chess

from chess_coach.db import Database
from chess_coach.motifs import record_motif_opportunities


def test_motif_facts_and_outcomes_preserve_versions() -> None:
    db = Database(":memory:")
    db.initialize()
    db.connection.execute(
        "INSERT INTO games (source_id, pgn, white, black, result) VALUES (?, ?, ?, ?, ?)",
        ("g1", "raw", "A", "B", "*"),
    )
    game_id = db.connection.execute("SELECT id FROM games").fetchone()[0]
    board = chess.Board("4k3/8/8/8/8/2N5/8/4K3 w - - 0 1")
    board.set_piece_at(chess.E4, chess.Piece(chess.KNIGHT, chess.WHITE))
    board.set_piece_at(chess.C5, chess.Piece(chess.ROOK, chess.BLACK))
    board.set_piece_at(chess.F6, chess.Piece(chess.BISHOP, chess.BLACK))
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (?, ?, ?, ?, ?)",
        (game_id, 1, board.fen(), "", ""),
    )
    position_id = db.connection.execute("SELECT id FROM positions").fetchone()[0]

    assert record_motif_opportunities(db, position_id, outcomes={"0": "failure"}) >= 1
    fact = db.connection.execute(
        "SELECT detector_version, fact_type FROM detector_facts"
    ).fetchone()
    evidence = db.connection.execute(
        "SELECT outcome, mapper_version FROM evidence_mappings"
    ).fetchone()
    assert tuple(fact) == ("0.1.0", "fork")
    assert tuple(evidence) == ("failure", "0.1.0")
