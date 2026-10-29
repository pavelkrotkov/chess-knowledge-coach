"""Classify the first two opposing pieces on a slider ray."""

import chess

from .material_values import VALUES
from .pin_ray_traversal import next_piece


def ray(board, attacker, square):
    target = board.piece_at(square)
    slider = board.piece_at(attacker)
    if not target or target.color == slider.color or target.piece_type not in VALUES:
        return None
    if square not in board.attacks(attacker):
        return None
    rear = next_piece(board, attacker, square)
    if rear is None:
        return None
    return _pin(board, square, rear, board.piece_at(rear), slider.color)


def _pin(board, square, rear, piece, color):
    if piece.color == color or piece.piece_type == chess.PAWN:
        return None
    absolute = piece.piece_type == chess.KING
    if not _qualifies(board, square, piece, absolute):
        return None
    return {"type": "absolute_pin" if absolute else "relative_pin", "pinned": square, "rear": rear}


def _qualifies(board, square, piece, absolute):
    if absolute:
        return board.is_pinned(piece.color, square)
    return VALUES[piece.piece_type] > VALUES[board.piece_at(square).piece_type]
