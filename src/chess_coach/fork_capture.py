"""Verify a concrete fork target capture and its immediate replies."""

import chess

from .material_capture_gain import capture_gain
from .material_lines import material
from .material_reply_guard import unresolved_reply


def capture(board, attacker, square, color, initial):
    target = board.piece_at(square)
    move = chess.Move(attacker, square)
    if target is None or target.color == color or move not in board.legal_moves:
        return None
    gain, reason, _ = capture_gain(board, move, target)
    if reason or unresolved_reply(board, move, initial):
        return None
    if material(board, color) - initial + gain < 3:
        return None
    return move.uci()
