"""Validate quiet defensive moves and immediate material counterplay."""

import chess

from .fork_defense_history import quiet_after
from .fork_defense_scan import scan
from .material_observation_fallback import _best_move
from .material_threats import check_options, threats


def safe_material(board, *, check=None):
    if check is not None:
        check()
    probe = threats(board, hypothetical=False, **check_options(check))
    return probe is not None and not probe["targets"] and not probe["uncertain"]


def safe_best(board, best_line, *, check=None, on_proof=None):
    best = _best_move(board, best_line)
    if not isinstance(best, chess.Move):
        return None
    after = quiet_after(board, best)
    if after is None:
        return None
    result = scan(after, check=check, on_proof=on_proof)
    if (
        result is None
        or result["uncertain"]
        or result["proven"]
        or not safe_material(after, check=check)
    ):
        return None
    return best
