"""Find opponent slider pins already present at the learner decision."""

import chess

from .pin_geometry_ray import ray


def existing(board):
    result = []
    for attacker in chess.SQUARES:
        piece = board.piece_at(attacker)
        if (
            not piece
            or piece.color == board.turn
            or piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN)
        ):
            continue
        for square in board.attacks(attacker):
            pin = ray(board, attacker, square)
            if pin:
                result.append((attacker, pin))
    return result
