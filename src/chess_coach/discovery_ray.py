"""Check that vacating a blocker actually reveals a slider line."""

import chess


def revealed(board, after, move, slider, color):
    if after.piece_at(slider) != board.piece_at(slider):
        return []
    results = []
    for target in after.attacks(slider):
        piece = after.piece_at(target)
        if piece is None or piece.color == color:
            continue
        if move.from_square not in chess.SquareSet(chess.between(slider, target)):
            continue
        if target in board.attacks(slider):
            continue
        results.append({"slider": slider, "target": target})
    return results
