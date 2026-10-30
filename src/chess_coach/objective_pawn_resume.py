"""Reconstruct a separately proved training reply from its event."""

from .objective_current import current
from .objective_pawn_binding import binding
from .objective_pawn_history import before_answer
from .objective_short_history import history_hash, validate_later_events


def resume(db, session, row, result):
    checked, events = current(db, row)
    board, move = before_answer(db, checked, events)
    binding(row, result, board, session)
    if result.get("move") != move.uci():
        raise ValueError("pawn continuation move changed")
    board.push(move)
    reply = board.parse_uci(result["continuation"]["reply"])
    if not reply or reply not in board.legal_moves:
        raise ValueError("pawn continuation unavailable")
    board.push(reply)
    data = result["continuation"]
    if board.fen() != data["fen"] or history_hash(board) != data["history_hash"]:
        raise ValueError("pawn continuation changed")
    validate_later_events(db, session, row["event_id"], board)
    return {"board": board, "reply": reply.uci()}
