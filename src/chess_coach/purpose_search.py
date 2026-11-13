"""Coordinate a scout and candidate-set comparison within one worker budget."""

import time

from .purpose_config import EARLY_CENTER, FINAL_SECONDS, SCOUT_SECONDS, VERSION
from .purpose_deadline import search_timeout
from .purpose_final import final
from .purpose_scout import scout


def search(engine, board, position, deadline, *, policy=VERSION):
    result = {"scope": "played-and-scout-nominee", "global_best": "unknown"}
    if board.legal_moves.count() < 2:
        return result, "forced_move"
    timeout = search_timeout(deadline, SCOUT_SECONDS)
    if timeout is None:
        return result, "worker_deadline"
    engine.timeout = timeout
    if policy == EARLY_CENTER:
        from .purpose_early_center import roots

        candidates = roots(board, position)
        if not candidates:
            return result, "no_distinct_nominee"
        result["scout"], nominee, issue = scout(engine, board, position, candidates)
    else:
        result["scout"], nominee, issue = scout(engine, board, position)
    if issue:
        return result, issue
    timeout = search_timeout(deadline, FINAL_SECONDS)
    if timeout is None:
        return result, "worker_deadline"
    engine.timeout = timeout
    result["final"], issue = final(engine, board, position, nominee, deadline)
    if time.monotonic() >= deadline:
        return result, "worker_deadline"
    return result, issue
