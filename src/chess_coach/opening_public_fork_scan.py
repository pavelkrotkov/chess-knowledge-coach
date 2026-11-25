"""Bound recorded-first fork root enumeration for one public game."""

import time

from .opening_public_fork_candidate import inspect
from .opening_public_fork_outcome import record
from .opening_public_fork_roots import roots
from .opening_public_proof_versions import ROOTS_PER_GAME


def scan(positions, rows, budget, deadline, *, safe=True, material_example=False):
    result = {
        "roots": 0,
        "geometries": 0,
        "unsupported": int(not safe),
        "material": 0,
        "mate": 0,
        "incomplete": False,
        "limit": None,
        "example": None,
    }
    candidates = iter(roots(positions))
    while result["roots"] < ROOTS_PER_GAME:
        if time.monotonic() >= deadline:
            raise TimeoutError("public fork deadline")
        try:
            ply, board, recorded, move = next(candidates)
        except StopIteration:
            return result
        result["roots"] += 1
        state, example = inspect(board, move, recorded, rows, ply, budget, deadline)
        if state == "limit":
            result["incomplete"] = True
            result["limit"] = "proofs"
            return result
        if state == "none":
            continue
        record(result, state, example)
        if material_example and state == "material":
            result["example"] = example
            material_example = False
    result["incomplete"] = True
    result["limit"] = "roots"
    return result
