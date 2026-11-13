"""Find a bounded independently proved exposure for a slide exercise."""

import chess

from .pin_exposure_geometry import exposed
from .related_pin_budget import take
from .related_pin_prevent_shape import features


def _eligible_bad(bad, good, pinned, ray):
    if bad.from_square != pinned["pinned"] or bad == good:
        return False
    return pinned["type"] != "relative_pin" or not chess.BB_SQUARES[bad.to_square] & ray


def witness(board, good, named, moves, budget, refutation):
    attacker, pinned = named
    ray = chess.between(attacker, pinned["rear"])
    for bad in moves:
        if not _eligible_bad(bad, good, pinned, ray):
            continue
        if not take(budget, "root_proofs"):
            return None
        proof = exposed(board, bad, [named])
        if proof:
            branch = {"move": good.uci(), "san": board.san(good), "counterfactual": bad.uci()}
            if refutation:
                branch["refutation"] = refutation
            return {**features(board, good, attacker, pinned), "origin": "slide"}, proof, branch
    return None
