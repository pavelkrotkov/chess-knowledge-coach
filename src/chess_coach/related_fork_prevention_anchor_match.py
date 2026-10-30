"""Select knight forks that preserve the original protected target roles."""

import chess


def matching(board, candidates, source):
    return {
        move: squares
        for move, squares in candidates.items()
        if board.piece_type_at(chess.Move.from_uci(move).from_square) == chess.KNIGHT
        and tuple(sorted(board.piece_type_at(square) for square in squares)) == source["target"]
    }
