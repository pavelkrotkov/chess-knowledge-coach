"""Prioritize at most one advisory check-evasion nominee per paired cycle."""

from .style_schedule_budget import CURRENT
from .style_schedule_clock import reached
from .style_schedule_nomination_game import inspect


# Both parsing and exact replay spend one history unit per stored ply.
def _fits(count):
    budget = CURRENT.get()
    return budget is None or count * 2 <= budget["limit"] - budget["used"]


def _collect(db, ordered, coverage):
    first = None
    for index, (game, color) in enumerate(ordered):
        if reached():
            coverage["nomination_unchecked_games"] = len(ordered) - index
            break
        try:
            checks, checked, count = inspect(db, game, color)
        except (ValueError, TypeError, IndexError):
            coverage["nomination_unknown_games"] += 1
            continue
        coverage["nomination_checked_decisions"] += checked
        coverage["nomination_games"] += bool(checks)
        coverage["nomination_turns"] += checks
        if first is None and checks and _fits(count):
            first = index
    return first


def prioritize(db, games, sequence):
    """Keep the full fallback order on alternate cycles and rotate paired starts."""
    # Pair prioritized and fallback cycles so every start advances fairly.
    offset = (sequence // 2) % len(games) if games else 0
    ordered = games[offset:] + games[:offset]
    coverage = {
        "nomination_games": 0,
        "nomination_turns": 0,
        "nomination_checked_decisions": 0,
        "nomination_unknown_games": 0,
        "nomination_unchecked_games": 0,
        "nomination_prioritized": False,
    }
    first = _collect(db, ordered, coverage)
    # All other games keep their original relative order, including unknowns.
    if sequence % 2 == 0 and first is not None:
        ordered.insert(0, ordered.pop(first))
        coverage["nomination_prioritized"] = True
    return ordered, coverage
