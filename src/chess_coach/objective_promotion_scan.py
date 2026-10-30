"""Scan every legal defense for a bounded next-move promotion."""

from .mate_proof_search import MAX_REPLIES
from .objective_promotion_leaf import promotion


def scan(board, budget):
    if board.can_claim_draw():
        return {"status": "unknown", "reason": "draw_claim"}
    if board.outcome(claim_draw=False) is not None:
        return {"status": "disproved", "reason": "terminal_before_promotion"}
    replies = sorted(board.legal_moves, key=lambda move: move.uci())
    if len(replies) > MAX_REPLIES:
        return {"status": "unknown", "reason": "reply_limit"}
    witnesses = []
    for reply in replies:
        if not budget.visit():
            return {"status": "unknown", "reason": "budget"}
        board.push(reply)
        try:
            found = promotion(board, budget)
        finally:
            board.pop()
        if found["status"] != "proved":
            return {**found, "reply": reply.uci()}
        witnesses.append({"reply": reply.uci(), "promotion": found["move"]})
    return {"status": "proved", "witnesses": witnesses}
