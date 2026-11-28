"""Inspect recorded roots in one original public game, never alternatives."""

from .opening_public_discovery_material_example import scan
from .opening_public_discovery_opportunity import scan as scan_opportunities
from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_mate_coverage import observation
from .opening_public_mate_game import _terminal


def inspect(db, row, binding, branch, deadline):
    opportunity = "discovery_opportunity" in binding["policy"]
    kind = "discovery_opportunity" if opportunity else "discovery_material"
    window = binding["policy"][kind]["window"]
    source, moves, rows, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=window
    )
    if not candidates:
        first, _ = bounds(binding["ply"], row[1], window)
        result = observation(censored, ended=row[1] < first, incomplete=True)
        return {**result, "roots_checked": 0, "geometry_unresolved": 0, "positions_unvisited": 0}
    if not safe and not _terminal(candidates, moves, row[2], censored):
        raise ValueError("discovery history unavailable")
    scanner = scan_opportunities if opportunity else scan
    return scanner(db, row, binding, source, moves, rows, candidates, censored, deadline)
