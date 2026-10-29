"""Exhaustive defender replies for bounded short-mate proof."""

from .mate_proof_moves import move_view

MAX_REPLIES = 100


def _winning_reply(board, budget):
    if board.outcome(claim_draw=False) is not None:
        return "disproved", None
    for move in sorted(board.legal_moves, key=lambda item: item.uci()):
        if not budget.visit():
            return "unknown", None
        view = move_view(board, move)
        board.push(move)
        mate = board.is_checkmate()
        board.pop()
        if mate:
            return "proved", view
    return "disproved", None


def _defenses(board, budget):
    if board.can_claim_draw() or board.outcome(claim_draw=False) is not None:
        return "disproved", []
    replies = sorted(board.legal_moves, key=lambda item: item.uci())
    if len(replies) > MAX_REPLIES:
        return "unknown", []
    witnesses = []
    for reply in replies:
        if not budget.visit():
            return "unknown", []
        view = move_view(board, reply)
        board.push(reply)
        status, mate = _winning_reply(board, budget)
        board.pop()
        if status != "proved":
            return status, []
        witnesses.append({"defense": view, "mate": mate})
    return "proved", witnesses
