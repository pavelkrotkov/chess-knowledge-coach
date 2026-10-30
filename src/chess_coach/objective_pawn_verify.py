"""Bind an owned queued answer to the announced pawn result."""

from .objective_capture_proof import unknown
from .objective_judge import _scope_reason
from .objective_pawn_judge import judge


def verify(board, move, request, events, clock, start, seconds, base, data):
    reason = _scope_reason(board, request, events)
    if reason:
        return unknown(base, reason)
    goal = data.get("result_goal")
    if type(goal) is not int or goal not in {0, 1}:
        return unknown(base, "objective_binding_unavailable")
    return judge(board, move, goal, clock, start, seconds, base, data)
