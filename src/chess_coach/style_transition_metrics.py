"""Count queens without conflating an imbalance with one queen per side."""

import chess


def queens(board):
    counts = [len(board.pieces(chess.QUEEN, side)) for side in chess.COLORS]
    return {"queens": sum(counts), "one_queen_each": counts == [1, 1]}
