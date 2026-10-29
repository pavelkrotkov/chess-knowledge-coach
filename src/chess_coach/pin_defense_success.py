"""Verify a counterfactual pin threat against the observed quiet defense."""

from .fork_defense_safety import quiet_after, safe_material
from .mate_proof_moves import immediate_mates
from .material_ambiguity import ambiguous
from .material_lines import continuation
from .pin_scan import scan


def success(board, actual, played_line, played_after):
    moves = list(board.legal_moves)
    if len(moves) > 64:
        return None
    for move in moves[:16]:
        if move == actual:
            continue
        after = quiet_after(board, move)
        found = _witness(after)
        if found:
            return _assess(board, actual, move, played_line, played_after, found)
    return None


def _witness(after):
    if after is None:
        return None
    found = scan(after)
    return found["proven"][0] if found and found["proven"] else None


def _assess(board, actual, move, played_line, played_after, witness):
    alternative = {"move": move.uci(), "san": board.san(move)}
    if immediate_mates(played_after) or not safe_material(played_after):
        return {
            **ambiguous(witness["type"], "other_immediate_threat_unresolved"),
            "proof": witness,
            "alternative": alternative,
        }
    line = continuation(board, played_line, actual.uci(), allow_checks=True)
    if line is None or line["material_delta"] < 0:
        return {
            **ambiguous(witness["type"], "compensation_unresolved"),
            "proof": witness,
            "alternative": alternative,
        }
    return {
        "kind": witness["type"],
        "outcome": "success",
        "proof": witness,
        "alternative": alternative,
        "played": line,
    }
