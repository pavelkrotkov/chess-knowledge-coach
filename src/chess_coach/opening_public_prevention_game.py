"""Replay one selected source history and bind prevention witnesses."""

from .objective_fork_defense_budget import BudgetExceeded
from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_prevention_steps import inspect_candidates

ORIGINS = ("pre_existing", "created")


def inspect(db, row, binding, move, start, deadline, check, charge):
    policy = binding["policy"]["prevention"]
    identity, moves, _, candidates, censored, safe = positions(
        db, row, binding, move, deadline, window=policy["window"]
    )
    first, last = bounds(binding["ply"], row[1], policy["window"])
    if row[1] < first:
        return {origin: ("ended_before_window", None) for origin in ORIGINS}, censored
    if not safe:
        return {origin: ("unsupported", None) for origin in ORIGINS}, censored
    return inspect_candidates(
        db,
        row,
        binding,
        identity,
        moves,
        first,
        last,
        candidates,
        censored,
        start,
        deadline,
        check,
        charge,
    )


def classified(db, row, binding, move, start, deadline, check, charge):
    try:
        return inspect(db, row, binding, move, start, deadline, check, charge)
    except BudgetExceeded:
        return {origin: ("incomplete", None) for origin in ORIGINS}, False
    except (ValueError, TypeError, KeyError, IndexError):
        return {origin: ("unsupported", None) for origin in ORIGINS}, False
