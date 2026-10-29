"""Check actual fork-loss evidence and a verified defensive alternative."""

from .material_lines import continuation, unopposed_material_loss


def failed(board, played, best, played_line, best_line, proof):
    actual = continuation(board, played_line, played.uci(), allow_checks=True, minimum_plies=4)
    alternative = continuation(board, best_line, best.uci())
    if actual is None or alternative is None:
        return None, "continuation_unavailable"
    if not _branch_matches(actual, proof):
        return None, "fork_consequence_unverified"
    if not unopposed_material_loss(best_line, played_line):
        return None, "engine_disagreement_or_compensation"
    if (
        alternative["material_delta"] < 0
        or actual["material_delta"] > alternative["material_delta"] - 3
    ):
        return None, "alternative_material_or_compensation"
    return {"played": actual, "best": alternative}, None


def _branch_matches(actual, proof):
    moves = actual["uci"]
    if len(moves) < 4 or moves[1] != proof["move"]:
        return False
    return any(
        item["reply"] == moves[2] and item["capture"] == moves[3] for item in proof["branches"]
    )
