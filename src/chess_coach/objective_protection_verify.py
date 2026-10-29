"""Bind a queued answer to its specified-piece objective."""

import chess

from .objective_judge import _scope_reason
from .objective_protection_after import unknown
from .objective_protection_judge import judge


def verify(board, move, request, events, clock, start, seconds, base, data):
    reason = _scope_reason(board, request, events)
    if reason:
        return unknown(base, reason)
    try:
        target = chess.parse_square(data["objective_target"])
    except (ValueError, KeyError, TypeError):
        return unknown(base, "objective_binding_unavailable")
    return judge(board, move, target, clock, start, seconds, base)
