"""Compare legal defenses against immediate mates using a shared proof budget."""

from .back_rank_defense_choices import choices
from .back_rank_defense_result import classify
from .back_rank_proposal import proposal
from .back_rank_scan import MAX_MOVES
from .mate_proof_moves import Budget

VERSION = "back-rank-defense-v1"
MAX_NODES = 6000


def observe(board, played, *, node_limit=MAX_NODES):
    if not 1 <= node_limit <= MAX_NODES:
        raise ValueError("invalid back-rank proof budget")
    if played not in board.legal_moves or board.outcome(claim_draw=False):
        raise ValueError("decision unavailable")
    alternatives = sorted(board.legal_moves, key=lambda move: move.uci())
    budget = Budget(node_limit)
    result = {
        "version": VERSION,
        "node_limit": node_limit,
        "reply_limit": MAX_MOVES,
        "draw_claim_available": board.can_claim_draw(),
    }
    if len(alternatives) > MAX_MOVES:
        return {**result, "status": "unknown", "reason": "alternative_limit", "nodes": 0}
    candidates = proposal(board, budget)
    items = choices(board, alternatives, budget)
    result.update({"nodes": budget.nodes, "alternatives": items, "played": played.uci()})
    if any(item["status"] == "unknown" for item in items):
        return {**result, "status": "unknown", "reason": "incomplete_alternatives"}
    return classify(result, candidates)
