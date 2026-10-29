"""Inspect the supported piece after a legal root move."""

from .pawn_structure_activity_recapture import recaptures
from .pawn_structure_immediate import _capture_status, _target_after


def after_root(board, root, target, square):
    move = board.parse_uci(root)
    pawn_square = _target_after(move, target)
    after = board.copy()
    after.push(move)
    piece = after.piece_at(square)
    owner = target["color"] == "white"
    if piece is None or piece.color != owner or after.turn == owner:
        return None
    supported = pawn_square is not None and square in after.attacks(pawn_square)
    check = _capture_status(after, square)
    return {
        "support_retained": supported,
        **check,
        "pawn_recaptures": recaptures(after, pawn_square, square, check),
    }
