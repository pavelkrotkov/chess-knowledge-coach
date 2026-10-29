"""Describe king alignment without drawing conclusions about the result."""

import chess


def describe(board):
    white, black = board.king(chess.WHITE), board.king(chess.BLACK)
    file_distance = abs(chess.square_file(white) - chess.square_file(black))
    rank_distance = abs(chess.square_rank(white) - chess.square_rank(black))
    return {
        "white_king": chess.square_name(white),
        "black_king": chess.square_name(black),
        "direct_opposition": (file_distance, rank_distance) in {(0, 2), (2, 0)},
        "side_to_move": "white" if board.turn == chess.WHITE else "black",
    }
