"""Certify a bounded unfamiliar corpus mate with reset move history."""

import chess

from .fact_fingerprint import canonical, digest
from .mate_proof import immediate_mates
from .puzzle_session_validate import solution_moves, validate_line

VERSION = "related-mate-two-assessment-v1"


def setup(db, version, key):
    row = db.connection.execute(
        """SELECT p.fen,p.solution,c.checksum FROM puzzles p JOIN puzzle_corpora c
        ON c.id=p.corpus_id WHERE c.version=? AND p.puzzle_id=? AND c.state='ready'""",
        (version, key),
    ).fetchone()
    if row is None:
        raise ValueError("assessment corpus unavailable")
    moves = solution_moves(row["solution"])
    prompt = validate_line(row["fen"], row["solution"])
    board = chess.Board(row["fen"])
    move = board.parse_uci(moves[0])
    if not board.is_zeroing(move):
        raise ValueError("assessment history unavailable")
    board.push(move)
    if board.fen() != prompt or board.is_game_over(claim_draw=True) or immediate_mates(board):
        raise ValueError("assessment requires a short mate")
    return (
        board,
        moves,
        digest(canonical([version, key, row["fen"], row["solution"], row["checksum"]])),
    )
