"""Qualify one current two-root opening experiment and its legal continuations."""

import chess

from .opening_experiment_line import branch

MAX_DISADVANTAGE = 50


def qualified(decision, choice, result):
    if result.get("status") != "complete":
        return None
    lines = {line["root_move"]: line for line in result["lines"]}
    played, alternative = lines.get(decision["played_uci"]), lines.get(choice["uci"])
    if played is None or alternative is None:
        return None
    if alternative["score_value"] < played["score_value"] - MAX_DISADVANTAGE:
        return None
    board = chess.Board(decision["fen"])
    original, revised = branch(board, played), branch(board, alternative)
    if original is None or revised is None:
        return None
    return {"played": original, "alternative": revised, "depth": played["depth"]}
