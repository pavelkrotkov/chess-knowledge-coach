"""Reconstruct a verified public promotion continuation."""

from .objective_current import current
from .objective_promotion_history import before_answer
from .objective_promotion_proof_binding import binding
from .objective_promotion_witness import choose
from .objective_short_history import validate_later_events


def resume(db, session, row, result):
    checked, events = current(db, row)
    board, move = before_answer(db, checked, events)
    binding(row, result, board, move)
    board.push(move)
    if move.promotion:
        return {"board": board, "complete": True}
    witness = choose(board, result["proof"])
    board.push(board.parse_uci(witness["reply"]))
    validate_later_events(db, session, row["event_id"], board)
    return {
        "board": board,
        "reply": witness["reply"],
        "promotion": witness["promotion"],
        "complete": False,
    }
