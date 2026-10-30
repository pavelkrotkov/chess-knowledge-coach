"""Find an actual legal anchor for a positional knight-fork threat."""

from .fork_defense_anchor import MAX_ANCHOR_MOVES
from .fork_defense_probe import hypothetical
from .fork_defense_safety import quiet_after, safe_material
from .related_fork_prevention_anchor_match import matching
from .related_fork_prevention_anchor_proof import prove
from .related_fork_prevention_budget import take


def anchor(board, source, budget):
    prepared = _prepare(board, source, budget)
    if prepared is None:
        return None
    candidates, moves = prepared
    local_proofs = 0
    for move in moves:
        if not take(budget, "anchors"):
            return None
        after = quiet_after(board, move)
        if after is None or not safe_material(after):
            continue
        proof, local_proofs = prove(after, candidates, budget, local_proofs)
        if budget["truncated"]:
            return None
        if proof:
            return after, proof
    return None


def _prepare(board, source, budget):
    candidates = hypothetical(board)
    if candidates is None:
        return None
    moves = list(board.legal_moves)
    if len(moves) > MAX_ANCHOR_MOVES:
        budget["truncated"] = True
        return None
    return matching(board, candidates, source), moves
