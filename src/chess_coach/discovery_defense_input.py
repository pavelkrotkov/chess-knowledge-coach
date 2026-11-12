"""Replay a current quiet decision and its available analysis lines."""

import chess

from .discovery_branch import unclear
from .discovery_line import lines
from .fork_defense_safety import quiet_after
from .material_observation_fallback import _best_move


def setup(board, played, best_line, played_line):
    actual, after = _played(board, played)
    if actual is None:
        return None
    best = _best_move(board, best_line)
    if not isinstance(best, chess.Move) or best == actual:
        return None
    compared = lines(board, best, actual, best_line, played_line)
    attack = _attack(after, compared)
    return (actual, after, best, compared, attack) if attack is not None else None


def _attack(after, compared):
    if not compared or len(compared["played"]["uci"]) < 2:
        return None
    return after.parse_uci(compared["played"]["uci"][1])


def _played(board, played):
    try:
        actual = board.parse_uci(played)
    except (ValueError, TypeError):
        return None, None
    after = quiet_after(board, actual)
    if not board.is_valid() or unclear(board) or after is None or unclear(after):
        return None, None
    return actual, after
