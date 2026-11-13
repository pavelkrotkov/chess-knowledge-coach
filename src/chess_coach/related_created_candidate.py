"""Reconstruct and reprove the one bound unfamiliar contrast."""

import chess

from .pawn_scope import history_known
from .puzzle_session_validate import legal_move, solution_moves
from .related_created_proof import nominations, prove


def recheck(db, row, selected, binding, source):
    board = _board(db, row, selected["prompt_fen"])
    witness = binding["created_witness"]
    good, bad = (board.parse_uci(witness[key]) for key in ("good", "bad"))
    capture = chess.Move.from_uci(witness["capture"])
    if not history_known(board) or (bad, capture) not in nominations(
        board, good, source["features"]
    ):
        raise ValueError("created exposure changed")
    if selected["lines"][0].split()[0] != good.uci() or prove(board, good, bad, capture) != witness:
        raise ValueError("created exposure proof changed")


def _board(db, row, fen):
    if row["source_type"] == "public":
        return chess.Board(fen)
    record = db.connection.execute(
        """SELECT p.fen,p.solution FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND p.puzzle_id=? AND c.state='ready'""",
        (row["source_version"], row["source_key"]),
    ).fetchone()
    if record is None:
        raise ValueError("practice setup unavailable")
    board = chess.Board(record["fen"])
    moves = solution_moves(record["solution"])
    board.push(legal_move(board, moves[0]))
    if board.fen() != fen:
        raise ValueError("practice setup changed")
    return board
