"""Replay original public games for newly allowed back-rank exposure."""

from .opening_public_created_backrank_scan import scan
from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_mate_coverage import observation
from .opening_public_mate_game import _terminal


def inspect(db, row, binding, branch, start, deadline):
    window = binding["policy"]["created_backrank"]["window"]
    source, moves, rows, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=window
    )
    if not candidates:
        first, _ = bounds(binding["ply"], row[1], window)
        result = observation(censored, ended=row[1] < first, incomplete=True)
        return {
            **result,
            "unknown_observations": 0,
            "nominated": 0,
            "positions_unvisited": 0,
            "interrupted": False,
        }
    if not safe and not _terminal(candidates, moves, row[2], censored):
        raise ValueError("back-rank history unavailable")
    return scan(db, row, binding, source, moves, rows, candidates, censored, start, deadline)
