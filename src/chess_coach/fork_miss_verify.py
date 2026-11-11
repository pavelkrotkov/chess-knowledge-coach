"""Resolve a proved game opportunity against current same-source analysis."""

import chess

from .fork_miss_candidate import candidate
from .material_lines import continuation
from .material_observation_fallback import _best_move
from .material_source import prepare

VERSION = "fork-game-miss-v1"


def _lines(board, actual, best, source):
    return (
        isinstance(best, chess.Move)
        and continuation(board, source["best"], best.uci(), allow_checks=True) is not None
        and continuation(board, source["played"], actual.uci(), allow_checks=True) is not None
    )


def verify(db, learner, position, outcome, check):
    source = prepare(db, position, learner)
    board = source["board"]
    actual = chess.Move.from_uci(source["context"]["played_move"])
    best = _best_move(board, source["best"])
    check()
    if actual not in board.legal_moves or not _lines(board, actual, best, source):
        return "unresolved", source
    if outcome == "played":
        return "played", source
    return candidate(board, actual, best, source, check), source
