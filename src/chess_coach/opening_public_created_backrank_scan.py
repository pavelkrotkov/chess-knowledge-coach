"""Scan source-ordered decisions for newly allowed back-rank mates."""

import time

from .back_rank_candidate import candidate
from .back_rank_defense import MAX_NODES, observe
from .objective_short_judge import DeadlineBudget
from .opening_public_created_backrank_example import example
from .opening_public_mate_coverage import observation
from .opening_public_mate_policy import check


def _observed(board, recorded, deadline):
    check(deadline)
    budget = DeadlineBudget(MAX_NODES, time.monotonic, deadline)
    result = observe(board.copy(stack=True), recorded, include_candidates=True, budget=budget)
    check(deadline)
    return result


def scan(db, row, binding, source, moves, rows, candidates, censored, start, deadline):
    unknown = nominated = 0
    for number, (ply, board, recorded) in enumerate(candidates):
        try:
            check(deadline)
            if not candidate(board, board.turn):
                continue
            nominated += 1
            observed = _observed(board, recorded, deadline)
            if (observed.get("status"), observed.get("outcome"), observed.get("origin")) != (
                "opportunity",
                "allows",
                "newly_allowed",
            ):
                unknown += 1
                continue
            value, interrupted = example(
                db,
                row,
                binding,
                source,
                moves,
                rows,
                ply,
                board,
                recorded,
                observed,
                start,
                deadline,
            )
        except TimeoutError:
            result = observation(censored, analyzed=bool(nominated), incomplete=True)
            return {
                **result,
                "unknown_observations": unknown,
                "nominated": nominated,
                "positions_unvisited": len(candidates) - number - 1,
                "interrupted": True,
            }
        result = observation(censored, example=value, analyzed=True, incomplete=interrupted)
        return {
            **result,
            "unknown_observations": unknown,
            "nominated": nominated,
            "positions_unvisited": len(candidates) - number - 1,
            "interrupted": interrupted,
        }
    result = observation(censored, analyzed=bool(nominated))
    return {
        **result,
        "unknown_observations": unknown,
        "nominated": nominated,
        "positions_unvisited": 0,
        "interrupted": False,
    }
