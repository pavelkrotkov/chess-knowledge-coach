"""Bound and classify one legal fork-defense answer."""

from .fork_defense_safety import quiet_after, safe_material
from .fork_defense_scan import scan
from .objective_capture_proof import unknown
from .objective_fork_defense_budget import ANSWER_UNITS, reserve
from .objective_fork_defense_result import correct


def assess(board, move, clock, start, seconds, base):
    after = quiet_after(board, move)
    if after is None or after.is_game_over(claim_draw=True) or not safe_material(after):
        return unknown(base, "defense_or_counterplay_unresolved")
    reserve(ANSWER_UNITS)
    result = scan(after)
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if result is None or result["proven"] or result["uncertain"]:
        return unknown(base, "fork_or_consequence_unresolved")
    return correct(board, move, seconds, base)
