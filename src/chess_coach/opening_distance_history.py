"""Collect one bounded same-side history sample for switching distance."""

import sqlite3

from .opening_preparation_history import (
    HISTORY_LIMIT,
    MAX_GAME_BYTES,
    MAX_GAMES,
    MAX_POSITIONS,
    TIME_VERSION,
    observed,
)
from .style_schedule_budget import BudgetExceeded, history_budget
from .tactical_course_budget import PreviewUnavailable


def history(db, learner, color, budget):
    try:
        with budget.scope(snapshot=True), history_budget(deadline=budget.expires):
            positions, edges, checked, skipped, flags = observed(db, learner, color)
        return {
            "positions": positions,
            "edges": edges,
            "checked_games": checked,
            "skipped_games": skipped,
            "uncertainty": flags,
            "incomplete": checked == 0 or skipped > 0 or any(flags.values()),
        }
    except (BudgetExceeded, PreviewUnavailable, sqlite3.Error, ValueError, TypeError):
        return None


def description(value):
    result = {
        "status": "unavailable"
        if value is None
        else "incomplete"
        if value["incomplete"]
        else "checked",
        "limits": {
            "games": MAX_GAMES,
            "positions_per_game": MAX_POSITIONS,
            "pgn_bytes": MAX_GAME_BYTES,
            "history_steps": HISTORY_LIMIT,
        },
        "time_projection": TIME_VERSION,
    }
    if value is not None:
        result.update(
            checked_games=value["checked_games"],
            skipped_games=value["skipped_games"],
            uncertainty=value["uncertainty"],
        )
    return result
