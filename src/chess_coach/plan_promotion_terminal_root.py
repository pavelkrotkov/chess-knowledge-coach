"""Recheck the original forced-promotion proof against its immutable source."""

from .objective_binding import matches
from .objective_current import _current
from .objective_events import response
from .objective_promotion_history import before_answer
from .objective_promotion_proof_binding import binding
from .objective_promotion_witness import choose


def _scope(session, data, request):
    shadow = {**dict(session), "status": "needs_verification"}
    return session["status"] == "objective_verified" and matches(shadow, data, request)


def resume(db, request, result):
    session, events = _current(db, request, _scope)
    shadow = {**dict(session), "current_fen": response(events[-1])["fen"]}
    board, move = before_answer(db, shadow, events)
    binding(request, result, board, move)
    if move.promotion:
        raise ValueError("terminal promotion history changed")
    board.push(move)
    witness = choose(board, result["proof"])
    board.push(board.parse_uci(witness["reply"]))
    return session, board, witness
