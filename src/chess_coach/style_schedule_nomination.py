"""Prioritize at most one advisory check-evasion nominee per paired cycle."""

from .style_schedule_clock import reached
from .style_schedule_identity import reserve
from .style_schedule_nomination_game import inspect
from .style_schedule_priority import firsts as _firsts


def _collect(db, ordered, coverage, reserved):
    first = structural_first = None
    nominations = []
    for index, (game, color) in enumerate(ordered):
        if reached():
            coverage["nomination_unchecked_games"] = len(ordered) - index
            break
        try:
            checks, structural, unknown, checked, count, early, identity = inspect(
                db, game, color, center=reserved
            )
        except (ValueError, TypeError, IndexError):
            if reached():
                coverage["nomination_unchecked_games"] = len(ordered) - index
                break
            coverage["nomination_unknown_games"] += 1
            continue
        coverage["nomination_checked_decisions"] += checked
        coverage["nomination_games"] += bool(checks)
        coverage["nomination_turns"] += checks
        coverage["structural_nomination_games"] += bool(structural)
        coverage["structural_nomination_turns"] += structural
        coverage["structural_nomination_unknown_turns"] += unknown
        first, structural_first = _firsts(first, structural_first, index, checks, structural, count)
        nominations.append((index, checks, early, count, identity))
        coverage["early_center_nomination_games"] += bool(early)
        coverage["early_center_nomination_turns"] += early
    return first, structural_first, nominations


def prioritize(db, games, sequence, *, identities=None):
    """Keep the full fallback order on alternate cycles and rotate paired starts."""
    # Reserved control cycles advance independently through every starting game.
    step = sequence // 4 if sequence % 4 == 1 else sequence // 2
    offset = step % len(games) if games else 0
    ordered = games[offset:] + games[:offset]
    coverage = {
        "nomination_games": 0,
        "nomination_turns": 0,
        "nomination_checked_decisions": 0,
        "nomination_unknown_games": 0,
        "nomination_unchecked_games": 0,
        "nomination_prioritized": False,
        "structural_nomination_games": 0,
        "structural_nomination_turns": 0,
        "structural_nomination_unknown_turns": 0,
        "structural_nomination_prioritized": False,
        "early_center_nomination_games": 0,
        "early_center_nomination_turns": 0,
        "early_center_nomination_prioritized": False,
    }
    reserved = sequence % 4 == 1
    first, structural_first, nominations = _collect(db, ordered, coverage, reserved)
    first = structural_first if structural_first is not None else first
    ordered, coverage["early_center_nomination_prioritized"] = reserve(
        ordered, nominations, identities, reserved
    )
    # All other games keep their original relative order, including unknowns.
    if sequence % 2 == 0 and first is not None:
        ordered.insert(0, ordered.pop(first))
        coverage["nomination_prioritized"] = True
        coverage["structural_nomination_prioritized"] = structural_first is not None
    return ordered, coverage
