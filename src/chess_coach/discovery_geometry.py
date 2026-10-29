"""Identify legal moves which uncover a friendly sliding attack."""

import chess

from .discovery_ray import revealed

SLIDERS = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def discoveries(board, move):
    if move not in board.legal_moves or board.is_game_over(claim_draw=True):
        return []
    color = board.turn
    after = board.copy()
    after.push(move)
    found = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != color or piece.piece_type not in SLIDERS:
            continue
        found.extend(revealed(board, after, move, square, color))
    return found
