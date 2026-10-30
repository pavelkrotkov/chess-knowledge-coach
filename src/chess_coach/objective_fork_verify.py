"""Validate the owned fork objective binding before proving a move."""

import chess

from .objective_capture_proof import unknown
from .objective_fork_judge import judge
from .objective_judge import _scope_reason


def verify(board, move, request, events, clock, start, seconds, base, data):
    reason = _scope_reason(board, request, events)
    if reason:
        return unknown(base, reason)
    try:
        attacker = chess.parse_square(data["fork_attacker"])
        anchor = chess.parse_square(data["fork_anchor"])
        if type(data["gain_threshold"]) is not int or data["gain_threshold"] != 3:
            raise ValueError
        if not board.piece_at(anchor):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return unknown(base, "objective_binding_unavailable")
    return judge(board, move, attacker, anchor, clock, start, seconds, base)
