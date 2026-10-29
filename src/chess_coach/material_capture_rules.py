"""Check material gain and continuation conflicts for a candidate capture."""

from .material_lines import unopposed_material_loss

MIN_GAIN = 3


def conflict(board, candidate, actual, best_line, played_line, best_pv, played_pv):
    proof = played_pv if actual == candidate else best_pv
    if _unsafe_continuation(board, candidate, proof):
        return "continuation_or_forcing_reply"
    if actual != candidate and not unopposed_material_loss(best_line, played_line):
        return "engine_disagreement_or_compensation"
    if actual != candidate and played_pv["material_delta"] > best_pv["material_delta"] - MIN_GAIN:
        return "alternative_material_or_compensation"
    return None


def _forcing_reply(board, move):
    after = board.copy()
    after.push(move)
    return any(
        not after.is_capture(reply) and after.gives_check(reply) for reply in after.legal_moves
    )


def _unsafe_continuation(board, candidate, proof):
    return (
        proof["uci"][0] != candidate.uci()
        or proof["material_delta"] < MIN_GAIN
        or _forcing_reply(board, candidate)
    )
