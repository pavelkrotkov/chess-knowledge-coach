"""Compare the observed alternative with the bounded fork witness."""

from .fork_result import ambiguous
from .material_lines import continuation, unopposed_material_loss


def miss(board, actual, best, best_line, played_line, proof):
    if board.gives_check(actual):
        return ambiguous("checking_alternative_unresolved")
    played = continuation(board, played_line, actual.uci())
    best_pv = continuation(board, best_line, best.uci(), allow_checks=True, minimum_plies=4)
    if played is None or best_pv is None:
        return ambiguous("continuation_unavailable")
    if not unopposed_material_loss(best_line, played_line):
        return ambiguous("engine_disagreement_or_compensation")
    if best_pv["material_delta"] < 3 or played["material_delta"] > best_pv["material_delta"] - 3:
        return ambiguous("alternative_material_or_compensation")
    return {"kind": "fork", "outcome": "failure", "proof": proof, "played": played, "best": best_pv}
