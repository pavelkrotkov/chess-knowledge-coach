"""Qualify one current two-root opening experiment and its legal continuations."""

import chess

from .opening_experiment_line import pair

MAX_DISADVANTAGE = 50


def assess(decision, choice, result):
    if result.get("status") != "complete":
        return None, "unavailable"
    lines = {line["root_move"]: line for line in result["lines"]}
    played, alternative = lines.get(decision["played_uci"]), lines.get(choice["uci"])
    if played is None or alternative is None:
        return None, "unavailable"
    if alternative["score_value"] < played["score_value"] - MAX_DISADVANTAGE:
        return None, "score_gap"
    branches, reason = pair(chess.Board(decision["fen"]), played, alternative)
    if branches is None:
        return None, reason
    return {**branches, "depth": played["depth"]}, None


def qualified(decision, choice, result):
    return assess(decision, choice, result)[0]
