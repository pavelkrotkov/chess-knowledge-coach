"""Qualify recorded-first pin roots from one original public history."""

from .opening_public_fork_later_history import positions
from .opening_public_fork_roots import roots
from .opening_public_fork_windows import WINDOW, bounds
from .opening_public_pin_coverage import example
from .opening_public_pin_policy import ROOTS_PER_GAME
from .pin_geometry import pins
from .pin_proof import proof as pin_proof


def inspect(db, row, binding, branch, deadline, check, charge):
    source, moves, _, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=binding["policy"]["pin"]["window"]
    )
    first, _ = bounds(binding["ply"], row[1], binding["policy"]["pin"]["window"])
    item = {
        "positions_available": len(candidates),
        "positions_inspected": 0,
        "roots": 0,
        "unsupported_proofs": 0,
        "short_record": row[1] < first + WINDOW - 1,
        "example": None,
    }
    if not candidates:
        item["incomplete"] = True
        return item, censored
    if not safe:
        item["unsupported_history"] = True
        return item, censored
    seen = set()
    for ply, board, recorded, move in roots(list(reversed(candidates))):
        check()
        if item["roots"] >= ROOTS_PER_GAME:
            item["incomplete"] = True
            return item, censored
        item["roots"] += 1
        seen.add(ply)
        item["positions_inspected"] = len(seen)
        for pin in pins(board, move):
            charge()
            proof = pin_proof(board, move, pin, check=check)
            if proof:
                item["incomplete"] = True
                item["example"] = example(
                    db, row, binding, source, moves, ply, board, recorded, move, proof
                )
                return item, censored
            item["unsupported_proofs"] += 1
    return item, censored
