"""Inspect one owned game's scoped capture opportunities without writes."""

import time

from .capture_game_counts import add, empty, finish
from .capture_game_proof import classify
from .short_mate_game_source import prepare, recheck

SECONDS = 5.0


def report(db, learner, game_id, *, seconds=SECONDS, clock=time.monotonic):
    if type(game_id) is not int or not 0 < game_id < 2**63 or not 0 < seconds <= SECONDS:
        raise ValueError("invalid inspection")
    if db.connection.in_transaction:
        raise ValueError("inspection requires an idle database")
    deadline = clock() + seconds
    source = prepare(db, learner, game_id)
    turns = [(context, board) for context, board in source["pairs"] if context["subject"]]
    counts = _inspect(turns, deadline, clock)
    recheck(db, learner, source)
    return {
        **counts,
        "game_id": game_id,
        "started_at": source["started_at"],
        "time_limit_seconds": seconds,
    }


def _inspect(turns, deadline, clock):
    counts = empty(len(turns))
    for context, board in turns:
        if clock() >= deadline:
            break
        outcome, reason = classify(board, context["played_move"], deadline, clock)
        add(counts, context, outcome, reason)
    return finish(counts)
