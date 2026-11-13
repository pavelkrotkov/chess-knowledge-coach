"""Prove a counterfactual pin and its supplied defense within the shared budget."""

from .objective_pin_prevent_created import judge
from .objective_pin_prevent_match import matches
from .objective_pin_prevent_origin import _created
from .pin_scan import scan
from .related_pin_budget import take
from .related_pin_created_geometry import shape


def check(board, good, bad, after, geometry, source, budget):
    if not take(budget, "root_proofs", len(geometry)):
        return None
    found = scan(after)
    if found is None:
        budget["unknown"] += 1
        return None
    for proof in found["proven"]:
        if proof["type"] != source["pin_kind"]:
            continue
        bound = _created(board, proof, bad, good)
        if not matches(proof, bad, bound):
            continue
        status, _reason, _proof = judge(board, good, bound)
        if status == "correct":
            return (
                shape(board, good, bound),
                proof,
                {"move": good.uci(), "san": board.san(good), "counterfactual": bad.uci()},
            )
        budget["unknown"] += status == "unresolved"
        return None
    return None
