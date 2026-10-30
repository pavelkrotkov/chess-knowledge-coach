"""Coordinate a scout and candidate-set comparison within one worker budget."""

import time

from .purpose_final import final
from .purpose_scout import scout


def search(engine, board, position, deadline):
    result = {"scope": "played-and-scout-nominee", "global_best": "unknown"}
    if board.legal_moves.count() < 2:
        return result, "forced_move"
    if time.monotonic() >= deadline:
        return result, "worker_deadline"
    result["scout"], nominee, issue = scout(engine, board, position)
    if issue:
        return result, issue
    if time.monotonic() >= deadline:
        return result, "worker_deadline"
    result["final"], issue = final(engine, board, position, nominee)
    if time.monotonic() >= deadline:
        return result, "worker_deadline"
    return result, issue
