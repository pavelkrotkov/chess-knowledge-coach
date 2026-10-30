"""Build scored synthetic search lines."""

import chess.engine

from tests.purpose_engine_lines import principal_variation


def candidate_line(board, move, index, mode, final):
    score = chess.engine.Mate(2) if mode == "mate" else chess.engine.Cp(index * 10)
    line = {
        "score": chess.engine.PovScore(score, board.turn),
        "pv": principal_variation(board, move, mode == "short" and final),
        "nodes": 210000 if final else 51000,
        "depth": 5 + (index if mode == "depth" else 0),
        "time": 0.1,
    }
    if mode == "bound":
        line["lowerbound"] = True
    return line
