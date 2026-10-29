"""Classify complete legal immediate-checkmate reply scans."""

from .back_rank_scan import mate_scan
from .objective_defense_outcome import classify
from .objective_short_judge import DeadlineBudget

MAX_NODES = 100


def after_move(board, clock, start, seconds, base):
    if clock() - start > seconds:
        return {**base, "status": "unresolved", "reason": "timeout"}
    if board.is_checkmate():
        return {
            **base,
            "status": "correct",
            "reason": "learner_checkmate",
            "replies_scanned": 0,
            "legal_replies": [],
        }
    if board.outcome(claim_draw=False):
        return {**base, "status": "unresolved", "reason": "terminal_position"}
    budget = DeadlineBudget(MAX_NODES, clock, start + seconds)
    scan = mate_scan(board, budget)
    if clock() - start > seconds:
        return {**base, "status": "unresolved", "reason": "timeout"}
    if scan["status"] != "complete":
        return {
            **base,
            "status": "unresolved",
            "reason": scan["reason"],
            "replies_scanned": budget.nodes,
        }
    result = classify(board, scan, budget.nodes, base)
    if clock() - start > seconds:
        return {**base, "status": "unresolved", "reason": "timeout"}
    return result
