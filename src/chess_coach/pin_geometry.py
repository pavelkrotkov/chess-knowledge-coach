"""Identify slider pins created by a legal move, without scoring their value."""

import chess

from .pin_geometry_ray import ray


def pins(board, move):
    if move not in board.legal_moves:
        return []
    piece = board.piece_at(move.from_square)
    if piece is None or piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return []
    after = board.copy()
    after.push(move)
    return [
        pin
        for square in chess.SQUARES
        if (pin := ray(after, move.to_square, square))
        and ray(board, move.from_square, square) != pin
    ]
