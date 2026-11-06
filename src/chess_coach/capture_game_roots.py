"""Qualify one direct capture under bounded immediate-reply rules."""

import chess

from .capture_game_replies import inspect as inspect_replies
from .material_capture_gain import capture_gain
from .material_exchange_rules import has_legal_recapture


def _scope(board, move):
    target = board.piece_at(move.to_square)
    if move.promotion or board.is_en_passant(move):
        return "unknown"
    if target is None or target.piece_type == chess.PAWN:
        return "outside"
    if board.is_check() or board.gives_check(move) or board.ep_square is not None:
        return "unknown"
    return "candidate"


def inspect(board, move):
    state = _scope(board, move)
    if state != "candidate":
        return state
    if has_legal_recapture(board, move):
        return "outside"
    gain, reason, _ = capture_gain(board, move, board.piece_at(move.to_square))
    if reason or gain is None:
        return "unknown"
    result = inspect_replies(board, move)
    return "outside" if result == "disproved" else result
