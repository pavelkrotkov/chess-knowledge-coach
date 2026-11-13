"""Reserve candidate line and pin-root work before inspecting it."""

import chess

from .related_pin_contract import LINE_LIMIT, PIN_GEOMETRY_LIMIT, ROOT_PROOF_LIMIT


def create():
    return {
        "lines": 0,
        "line_limit": LINE_LIMIT,
        "root_proofs": 0,
        "root_proof_limit": ROOT_PROOF_LIMIT,
        "pin_geometry_limit": PIN_GEOMETRY_LIMIT,
        "unknown": 0,
        "truncated": False,
    }


def take(budget, kind, amount=1):
    limit = budget[{"lines": "line_limit", "root_proofs": "root_proof_limit"}[kind]]
    if budget[kind] + amount > limit:
        budget["truncated"] = True
        return False
    budget[kind] += amount
    return True


def slide_root(budget, move, attacker, pinned):
    if move.from_square != pinned["pinned"] or not (
        chess.between(attacker, pinned["rear"]) & chess.BB_SQUARES[move.to_square]
    ):
        return False
    return pinned["type"] != "absolute_pin" or take(budget, "root_proofs")
