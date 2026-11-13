"""Bounded royal-skewer proofs for one already replayed decision."""

import chess

from .pawn_scope import history_known
from .skewer_game_geometry import rear
from .skewer_game_line import witness

MAX_ROOTS = 16


def inspect(board, played, deadline, clock):
    """Return one proved checking root or an honest bounded empty result."""
    if not board.is_valid() or not history_known(board) or board.is_game_over(claim_draw=True):
        return None, "unsupported history"
    roots = sorted(
        (
            move
            for move in board.legal_moves
            if board.piece_type_at(move.from_square) in (chess.ROOK, chess.BISHOP, chess.QUEEN)
            and board.gives_check(move)
        ),
        key=lambda move: move.uci(),
    )
    return _search(board, played, roots, deadline, clock)


def _search(board, played, roots, deadline, clock):
    for move in roots[:MAX_ROOTS]:
        if clock() >= deadline:
            return None, "time limit"
        geometry = rear(board, move)
        if geometry is None:
            continue
        after, (target, piece) = geometry
        proof = witness(board, move, after, target, piece, deadline, clock)
        if proof:
            (reply, capture), replies = proof
            return {
                "root": board.san(move),
                "played": move.uci() == played,
                "target": chess.piece_name(piece.piece_type),
                "square": chess.square_name(target),
                "reply": reply,
                "capture": capture,
                "replies": replies,
            }, None
    reason = (
        "time limit"
        if clock() >= deadline
        else ("root limit" if len(roots) > MAX_ROOTS else "no supported proof")
    )
    return None, reason
