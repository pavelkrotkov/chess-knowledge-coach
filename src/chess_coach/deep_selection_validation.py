"""Validate the public selection request and its independent budgets."""

import math


def validate_request(game_ids, per_game, total, cp_gap, wdl_gap):
    _validate_games(game_ids)
    _validate_limits(per_game, total)
    _validate_gaps(cp_gap, wdl_gap)


def _validate_games(game_ids):
    if not isinstance(game_ids, (list, tuple)) or not 1 <= len(game_ids) <= 20:
        raise ValueError("supply 1 to 20 game IDs")
    if any(type(item) is not int or item < 1 for item in game_ids) or len(set(game_ids)) != len(
        game_ids
    ):
        raise ValueError("game IDs must be positive and distinct")


def _validate_limits(per_game, total):
    if any(type(value) is not int or not 1 <= value <= 100 for value in (per_game, total)):
        raise ValueError("selection limits must be integers from 1 to 100")


def _validate_gaps(cp_gap, wdl_gap):
    if type(cp_gap) is not int or not 1 <= cp_gap <= 10000:
        raise ValueError("centipawn gap must be an integer from 1 to 10000")
    if (
        isinstance(wdl_gap, bool)
        or not isinstance(wdl_gap, (int, float))
        or not math.isfinite(wdl_gap)
        or not 0 < wdl_gap <= 1
    ):
        raise ValueError("WDL gap must be finite and greater than zero, up to one")
