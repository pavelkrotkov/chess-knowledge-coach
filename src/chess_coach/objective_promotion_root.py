"""Prove the announced immediate or bounded forced promotion."""

from .mate_proof import MAX_NODES
from .objective_capture_proof import unknown
from .objective_promotion_contract import FORCE, NOW
from .objective_promotion_result import classify
from .objective_promotion_scan import scan
from .objective_short_judge import DeadlineBudget


def evaluate(board, move, objective, clock, start, seconds, result):
    if clock() - start > seconds:
        return unknown(result, "timeout")
    if move.promotion:
        return {**result, "status": "correct", "reason": "promotion_performed", "witnesses": []}
    if objective == NOW:
        return {**result, "status": "incorrect", "reason": "not_immediate_promotion"}
    if objective != FORCE:
        return unknown(result, "unsupported_objective")
    budget = DeadlineBudget(MAX_NODES, clock, start + seconds)
    board.push(move)
    try:
        proof = scan(board, budget)
    finally:
        board.pop()
    return classify(proof, result, budget.nodes, clock, start, seconds)
