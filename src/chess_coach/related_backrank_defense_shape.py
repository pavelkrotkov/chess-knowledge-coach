"""Describe the legal mating witness relative to the defending king."""

import chess

from .back_rank_terminal import terminal


def shape(board, quiet, mating_move):
    replay = board.copy(stack=True)
    replay.push(replay.parse_uci(quiet))
    replay.push(replay.parse_uci(mating_move))
    geometry = terminal(replay)
    if geometry is None:
        raise ValueError("back-rank mate unavailable")
    king = chess.parse_square(geometry["king"])
    forward = 1 if replay.turn == chess.WHITE else -1
    blocked = tuple(
        sorted(
            (
                chess.square_file(chess.parse_square(square)) - chess.square_file(king),
                forward * (chess.square_rank(chess.parse_square(square)) - chess.square_rank(king)),
            )
            for square in geometry["occupied_flights"]
        )
    )
    checkers = tuple(
        sorted(
            (
                replay.piece_type_at(chess.parse_square(square)),
                1
                if chess.square_file(chess.parse_square(square)) > chess.square_file(king)
                else -1,
            )
            for square in geometry["checkers"]
        )
    )
    return chess.square_file(king), blocked, checkers
