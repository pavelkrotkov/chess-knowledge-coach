"""Observe short mates against a verified original public history."""

import time

from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_mate_coverage import observation
from .opening_public_mate_game import _terminal
from .opening_public_mate_policy import check
from .opening_public_short_mate_example import example, proof


def inspect(db, row, binding, branch, start, deadline):
    window = binding["policy"]["short_mate"]["window"]
    source, moves, rows, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=window
    )
    if not candidates:
        first, _ = bounds(binding["ply"], row[1], window)
        return observation(censored, ended=row[1] < first, incomplete=True)
    if not safe and not _terminal(candidates, moves, row[2], censored):
        raise ValueError("short-mate history unavailable")
    incomplete = False
    for ply, board, recorded in candidates:
        check(deadline)
        result = proof(board, deadline)
        incomplete |= result["incomplete"]
        if result["supported"]:
            value = example(db, row, binding, source, moves, rows, ply, board, recorded, result)
            return observation(censored, example=value, analyzed=True, incomplete=incomplete)
        if time.monotonic() >= deadline:
            return observation(censored, analyzed=True, incomplete=True)
    return observation(censored, analyzed=True, incomplete=incomplete)
