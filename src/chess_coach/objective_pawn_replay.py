"""Replay a previously proved pawn turn and reply."""

from .objective_events import response
from .objective_pawn_play import play
from .objective_pawn_prior import proved


def replay(db, session, event, board, prior_reply):
    detail = response(event)
    if event["kind"] == "hint" or detail.get("feedback") == "illegal":
        if detail.get("fen") != board.fen():
            raise ValueError("pawn history changed")
        return prior_reply
    input_check(event, board, prior_reply)
    result = proved(db, session, event, board)
    return play(board, event, detail, result)


def input_check(event, board, prior_reply):
    detail = response(event)
    if event["kind"] != "move" or detail.get("feedback") != "needs_verification":
        raise ValueError("pawn history unavailable")
    if prior_reply is not None and (
        detail.get("opponent_before_move") != prior_reply or detail.get("input_fen") != board.fen()
    ):
        raise ValueError("pawn reply history changed")
