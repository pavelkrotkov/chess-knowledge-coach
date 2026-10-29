"""Scan each legal learner move with one shared budget."""

from .back_rank_scan import mate_scan
from .mate_proof_moves import move_view


def choices(board, moves, budget):
    result = []
    for move in moves:
        view = move_view(board, move)
        if not budget.visit():
            result.append({"move": view, "status": "unknown", "reason": "node_limit"})
            break
        quiet = not (board.is_capture(move) or board.gives_check(move) or move.promotion)
        board.push(move)
        if board.outcome(claim_draw=False):
            scan = {"status": "terminal"}
        else:
            scan = mate_scan(board, budget)
        board.pop()
        result.append({"move": view, "quiet": quiet, **scan})
    return result


def anchors(items, candidates):
    if not candidates:
        return []
    result = []
    for item in items:
        if item["status"] != "complete" or not item["quiet"]:
            continue
        result.extend(
            {"alternative": item["move"], "mate": mate}
            for mate in item["back_rank"]
            if mate["move"]["uci"] in candidates
        )
    return result
