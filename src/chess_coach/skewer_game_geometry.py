"""Identify a single rear piece behind the checked king."""

import chess


def rear(board, move):
    after = board.copy()
    after.push(move)
    king = after.king(after.turn)
    if king is None or set(after.checkers()) != {move.to_square}:
        return None
    behind = [
        square
        for square in chess.SquareSet(after.occupied)
        if chess.between(move.to_square, square) & chess.BB_SQUARES[king]
    ]
    if len(behind) != 1:
        return None
    piece = after.piece_at(behind[0])
    if piece.color != after.turn:
        return None
    return after, (behind[0], piece)
