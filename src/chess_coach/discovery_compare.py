"""Classify only proved outcomes between legal decision roots."""

from .discovery_geometry import discoveries
from .discovery_proof import prove
from .material_ambiguity import ambiguous


def compare(board, actual, best, lines):
    actual_proofs = prove(board, actual)
    if actual_proofs:
        return _result("success", actual_proofs, lines)
    best_proofs = prove(board, best)
    if best_proofs and best_proofs[0]["mate"] and not _mate(board, actual):
        return _result("failure", best_proofs, lines)
    return unresolved(board, actual, best, "consequence_or_alternative_unresolved")


def _result(outcome, proofs, lines):
    return {
        "kind": "discovered_attack",
        "outcome": outcome,
        "proof": proofs[0],
        "proofs": proofs,
        **lines,
    }


def unresolved(board, actual, best, reason):
    for move in (actual, best):
        if move is not None and move is not False and discoveries(board, move):
            return ambiguous("discovered_attack", reason)
    return None


def _mate(board, move):
    child = board.copy()
    child.push(move)
    return child.is_checkmate()
