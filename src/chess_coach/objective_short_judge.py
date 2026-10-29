"""Prove a single alternative within the announced two-move horizon."""

import json

from .mate_proof import MAX_NODES, VERSION, _root
from .mate_proof_moves import Budget
from .mate_proof_search import MAX_REPLIES
from .objective_short_history import history_hash


def judge(board, move, clock, start, seconds, base):
    history = history_hash(board)
    budget = DeadlineBudget(MAX_NODES, clock, start + seconds)
    proof = _root(board, move, budget)
    limits = {
        "plies": 3,
        "nodes": budget.nodes,
        "node_limit": MAX_NODES,
        "reply_limit": MAX_REPLIES,
        "compute_timeout_seconds": seconds,
    }
    result = {**base, "history_hash": history, "limits": limits, "proof_version": VERSION}
    if clock() - start > seconds:
        return {**result, "status": "unresolved", "reason": "timeout"}
    if proof["status"] == "unknown":
        return {**result, "status": "unresolved", "reason": "proof_budget"}
    if proof["status"] == "disproved":
        return {**result, "status": "incorrect", "reason": "refuted_within_two"}
    if len(json.dumps(proof, sort_keys=True).encode()) > 65536:
        return {**result, "status": "unresolved", "reason": "proof_size_limit"}
    return {**result, "status": "correct", "reason": "mate_within_two_proved", "proof": proof}


class DeadlineBudget(Budget):
    def __init__(self, limit, clock, deadline):
        super().__init__(limit)
        self.clock = clock
        self.deadline = deadline

    def visit(self):
        return self.clock() <= self.deadline and super().visit()
