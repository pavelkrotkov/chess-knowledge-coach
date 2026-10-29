"""Find valuable targets for a legally played fork shape."""

import chess

from .material_values import VALUES


def geometry(board, move):
    after = board.copy()
    after.push(move)
    attacked = [
        square
        for square in after.attacks(move.to_square)
        if _valuable(after.piece_at(square), board.turn)
    ]
    if len(attacked) < 2:
        return None
    return after, tuple(sorted(attacked))


def _valuable(piece, color):
    return (
        piece is not None
        and piece.color != color
        and (piece.piece_type == chess.KING or VALUES.get(piece.piece_type, 0) >= 3)
    )
