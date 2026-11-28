"""Inspect recorded roots in one original public game, never alternatives."""

from .opening_public_discovery_material_example import scan
from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_mate_coverage import observation
from .opening_public_mate_game import _terminal


def inspect(db, row, binding, branch, deadline):
    window = binding["policy"]["discovery_material"]["window"]
    source, moves, rows, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=window
    )
    if not candidates:
        first, _ = bounds(binding["ply"], row[1], window)
        result = observation(censored, ended=row[1] < first, incomplete=True)
        return {**result, "roots_checked": 0, "geometry_unresolved": 0, "positions_unvisited": 0}
    if not safe and not _terminal(candidates, moves, row[2], censored):
        raise ValueError("discovery history unavailable")
    return scan(db, row, binding, source, moves, rows, candidates, censored, deadline)
