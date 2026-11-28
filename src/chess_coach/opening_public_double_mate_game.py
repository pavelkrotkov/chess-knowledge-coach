"""Observe double-check immediate mates in one original public game."""

from .opening_public_double_mate_example import certificate, classify
from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_mate_coverage import observation
from .opening_public_mate_game import _terminal
from .opening_public_mate_policy import check


def inspect(db, row, binding, branch, start, deadline):
    window = binding["policy"]["double_mate"]["window"]
    source, moves, rows, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=window
    )
    if not candidates:
        first, _ = bounds(binding["ply"], row[1], window)
        return observation(censored, ended=row[1] < first, incomplete=True)
    if not safe and not _terminal(candidates, moves, row[2], censored):
        raise ValueError("double-check mate history unavailable")
    for ply, board, recorded in candidates:
        check(deadline)
        qualified = classify(board, deadline)
        if qualified:
            value = certificate(
                db,
                row,
                binding,
                source,
                moves,
                rows,
                ply,
                board,
                recorded,
                qualified,
                start,
                deadline,
            )
            return observation(censored, example=value, analyzed=True)
    return observation(censored, analyzed=True)
