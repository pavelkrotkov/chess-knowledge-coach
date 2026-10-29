"""Verify one pawn move against a bounded local WDL proof."""

from . import pawn_proof
from .objective_capture_proof import unknown
from .objective_pawn_proof import inspect
from .objective_pawn_result import classify
from .objective_pawn_scope import reason as scope_reason


def judge(board, move, goal, clock, start, seconds, base, data):
    reason = scope_reason(board, move, data, clock, start, seconds)
    if reason:
        return unknown(base, reason)
    proof = inspect(board, node_limit=pawn_proof.MAX_NODES // 2)
    if clock() - start > seconds:
        return unknown(base, "timeout")
    return classify(board, move, goal, proof, clock, start, seconds, base)
