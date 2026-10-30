"""Coordinate a scout and candidate-set comparison within one worker budget."""

import time

from .purpose_config import FINAL_SECONDS, SCOUT_SECONDS
from .purpose_deadline import search_timeout
from .purpose_final import final
from .purpose_scout import scout


def search(engine, board, position, deadline):
    result = {"scope": "played-and-scout-nominee", "global_best": "unknown"}
    if board.legal_moves.count() < 2:
        return result, "forced_move"
    timeout = search_timeout(deadline, SCOUT_SECONDS)
    if timeout is None:
        return result, "worker_deadline"
    engine.timeout = timeout
    result["scout"], nominee, issue = scout(engine, board, position)
    if issue:
        return result, issue
    timeout = search_timeout(deadline, FINAL_SECONDS)
    if timeout is None:
        return result, "worker_deadline"
    engine.timeout = timeout
    result["final"], issue = final(engine, board, position, nominee)
    if time.monotonic() >= deadline:
        return result, "worker_deadline"
    return result, issue
