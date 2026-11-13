"""Reserve bounded line replay and counterfactual proof work."""

import time

from .related_created_proof import prove
from .related_pin_prevent_line import _replay

ROOT_LIMIT = 64
LINE_LIMIT = 64


def line(board, line, good, moves, budget):
    if not _take(budget, "lines", LINE_LIMIT):
        return None
    _replay(board, line)
    for bad, capture in moves:
        if not _take(budget, "roots", ROOT_LIMIT):
            return None
        witness = prove(board, good, bad, capture)
        if time.monotonic() >= budget["deadline"]:
            budget["truncated"] = True
            return None
        if witness is not None:
            return witness
    return None


def _take(budget, kind, limit):
    if budget[kind] >= limit or time.monotonic() >= budget["deadline"]:
        budget["truncated"] = True
        return False
    budget[kind] += 1
    return True
