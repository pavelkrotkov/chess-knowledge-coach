"""Validate quiet defensive moves and immediate material counterplay."""

import chess

from .fork_defense_scan import scan
from .material_observation_fallback import _best_move
from .material_threats import threats


def safe_material(board):
    probe = threats(board, hypothetical=False)
    return probe is not None and not probe["targets"] and not probe["uncertain"]


def quiet_after(board, move):
    if board.is_capture(move) or board.gives_check(move) or move.promotion:
        return None
    after = board.copy()
    after.push(move)
    if after.ep_square is not None or after.is_repetition(2) or after.is_fifty_moves():
        return None
    return after


def safe_best(board, best_line):
    best = _best_move(board, best_line)
    if not isinstance(best, chess.Move):
        return None
    after = quiet_after(board, best)
    if after is None:
        return None
    result = scan(after)
    if result is None or result["uncertain"] or result["proven"] or not safe_material(after):
        return None
    return best
