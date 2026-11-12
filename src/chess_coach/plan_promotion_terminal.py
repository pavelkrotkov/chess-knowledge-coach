"""Revalidate the final legal move after a proved promotion setup."""

from .objective_events import response
from .plan_promotion_events import before_final
from .plan_promotion_terminal_root import resume


def _final(session, board, witness, event):
    detail = response(event)
    if event["kind"] != "move" or detail.get("feedback") != "objective_verified":
        return False
    if (
        detail.get("input_fen") != board.fen()
        or detail.get("opponent_before_move") != witness["reply"]
    ):
        return False
    move = board.parse_uci(event["submitted_move"])
    if not move.promotion or move not in board.legal_moves:
        return False
    board.push(move)
    return detail.get("fen") == session["current_fen"] == board.fen()


def verified(db, request, result, later):
    if not later:
        return False
    session, board, witness = resume(db, request, result)
    return before_final(later[:-1], board) and _final(session, board, witness, later[-1])
