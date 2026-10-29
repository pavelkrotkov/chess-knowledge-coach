"""Identify valuable targets attacked by the moved piece after a legal fork move."""

import chess

from .material_values import VALUES


def targets(board, move):
    if not _eligible(board, move):
        return None
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


def _eligible(board, move):
    return (
        move in board.legal_moves
        and not board.is_capture(move)
        and not move.promotion
        and not board.is_check()
        and board.ep_square is None
        and not board.is_repetition(2)
        and not board.is_fifty_moves()
    )


def _valuable(piece, color):
    return (
        piece is not None
        and piece.color != color
        and (piece.piece_type == chess.KING or VALUES.get(piece.piece_type, 0) >= 3)
    )
