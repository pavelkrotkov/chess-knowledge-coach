"""Verify the announced owned quiet relative-slide objective."""

from .objective_capture_proof import unknown
from .objective_judge import _scope_reason
from .objective_pin_prevent_budget import BudgetExceeded, take_answer
from .objective_pin_slide_budget import scope
from .objective_pin_slide_result import assess
from .objective_pin_slide_scope import _quiet


def verify(board, move, request, events, clock, start, seconds, base, data):
    with scope():
        reason = _scope_reason(board, request, events)
        if reason:
            return unknown(base, reason)
        if clock() - start > seconds:
            return unknown(base, "timeout")
        if not _quiet(board, move):
            return unknown(base, "move_or_history_unresolved")
        try:
            take_answer()
            return assess(board, move, data["pin_prevention"], clock, start, seconds, base)
        except BudgetExceeded:
            raise
        except (KeyError, TypeError, ValueError, IndexError):
            return unknown(base, "pin_slide_unavailable")
