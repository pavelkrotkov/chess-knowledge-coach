"""Find a legal next promotion under the shared deadline budget."""


def promotion(board, budget):
    if board.can_claim_draw():
        return {"status": "unknown", "reason": "draw_claim"}
    if board.outcome(claim_draw=False) is not None:
        return {"status": "disproved", "reason": "terminal_before_promotion"}
    for move in sorted(board.legal_moves, key=lambda item: item.uci()):
        if not budget.visit():
            return {"status": "unknown", "reason": "budget"}
        if move.promotion:
            return {"status": "proved", "move": move.uci()}
    return {"status": "disproved", "reason": "no_legal_promotion"}
