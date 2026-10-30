"""Dispatch bounded prevention proofs while preserving unknown outcomes."""

from .material_exchange_rules import unclear
from .objective_capture_proof import unknown
from .objective_judge import _scope_reason
from .objective_pin_prevent_budget import BudgetExceeded, scope, take_answer
from .objective_pin_prevent_created import judge as created
from .objective_pin_prevent_existing import judge as existing
from .objective_pin_prevent_preflight import reserve
from .objective_short_history import history_hash


def verify(board, move, request, events, clock, start, seconds, base, data):
    with scope():
        return _verify(board, move, request, events, clock, start, seconds, base, data)


def _verify(board, move, request, events, clock, start, seconds, base, data):
    reason = _scope_reason(board, request, events)
    if reason:
        return unknown(base, reason)
    try:
        budget = reserve(board)
        named = data["pin_prevention"]
        verifier = {"existing": existing, "created": created}[named["origin"]]
        _require_legal(board, move)
        if clock() - start > seconds:
            return unknown(base, "timeout")
        take_answer()
        status, why, proof = verifier(board, move, named)
        if clock() - start > seconds:
            return unknown(base, "timeout")
    except BudgetExceeded:
        raise
    except (KeyError, TypeError, ValueError, IndexError):
        return unknown(base, "pin_prevention_unavailable")
    return {
        **base,
        "status": status,
        "reason": why,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "proof": proof,
        "work_reservation": budget,
    }


def _require_legal(board, move):
    if unclear(board) or board.ep_square is not None or move not in board.legal_moves:
        raise ValueError
