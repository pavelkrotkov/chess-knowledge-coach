"""Inspect bounded royal-skewer opportunities in one original public game."""

import time

from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_mate_coverage import observation
from .opening_public_mate_game import _terminal
from .opening_public_mate_policy import check
from .opening_public_skewer_example import example
from .skewer_game_proof import inspect as inspect_proof


def inspect(db, row, binding, branch, start, deadline):
    window = binding["policy"]["skewer"]["window"]
    source, moves, rows, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=window
    )
    if not candidates:
        first, _ = bounds(binding["ply"], row[1], window)
        return observation(censored, ended=row[1] < first, incomplete=True)
    if not safe and not _terminal(candidates, moves, row[2], censored):
        raise ValueError("skewer history unavailable")
    incomplete = False
    for ply, board, recorded in candidates:
        check(deadline)
        proof, reason = inspect_proof(board, recorded.uci(), deadline, time.monotonic)
        if proof is not None:
            value = example(db, row, binding, source, moves, rows, ply, board, recorded, proof)
            return observation(censored, example=value, analyzed=True, incomplete=incomplete)
        incomplete = True
        if reason == "time limit":
            return observation(censored, analyzed=True, incomplete=True)
    return observation(censored, analyzed=True, incomplete=incomplete)
