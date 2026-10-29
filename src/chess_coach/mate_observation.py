"""Bounded attacking mate observations; no ability or intent is inferred."""

from .mate_proof import immediate_mates, move_view, prove_short_mates


def observe(board, played, *, short_candidate):
    mates = immediate_mates(board)
    played_view = move_view(board, played)
    board.push(played)
    checkmate, stalemate = board.is_checkmate(), board.is_stalemate()
    board.pop()
    proof = prove_short_mates(board) if mates or short_candidate else None
    facts = {
        "played": played_view,
        "immediate_mates": mates,
        "played_checkmate": checkmate,
        "played_stalemate": stalemate,
        "immediate_mate_not_played": bool(mates) and not checkmate,
        "proof": proof,
    }
    return _classify(facts, proof, played)


def _classify(facts, proof, played):
    if proof is None:
        return {**facts, "status": "unknown", "reason": "short_mate_not_selected"}
    proved = [root for root in proof["alternatives"] if root["status"] == "proved"]
    if not proved:
        return {**facts, "status": proof["status"], "reason": "bounded_short_mate_search"}
    root = next(root for root in proof["alternatives"] if root["move"]["uci"] == played.uci())
    outcome = {"proved": "success", "disproved": "failure", "unknown": "ambiguous"}[root["status"]]
    return {**facts, "status": "opportunity", "outcome": outcome}
