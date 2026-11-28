"""Observe immediate mates against a single verified original public history."""

import json

from .mate_proof_moves import immediate_mates
from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_mate_coverage import observation
from .opening_public_mate_example import example
from .opening_public_mate_policy import check


def _terminal(candidates, moves, context, censored):
    if censored:
        return False
    ply, board, _ = candidates[-1]
    if len(moves) - ply not in (0, 1):
        return False
    after = board.copy(stack=True)
    for uci in moves[ply - 1 :]:
        after.push_uci(uci)
    return after.is_checkmate() and json.loads(context).get("Result") == after.result()


def inspect(db, row, binding, branch, start, deadline):
    source, moves, rows, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=binding["policy"]["mate"]["window"]
    )
    if not candidates:
        first, _ = bounds(binding["ply"], row[1], binding["policy"]["mate"]["window"])
        return observation(censored, ended=row[1] < first, incomplete=True)
    if not safe and not _terminal(candidates, moves, row[2], censored):
        raise ValueError("mate history unavailable")
    for ply, board, recorded in candidates:
        check(deadline)
        mates = immediate_mates(board)
        check(deadline)
        if mates:
            value = example(
                db, row, binding, source, moves, rows, ply, board, recorded, mates, start, deadline
            )
            return observation(censored, example=value, analyzed=True)
    return observation(censored, analyzed=True)
