"""Recognize verified alternative roots and their played mating continuations."""

from .coaching_short_request import verified
from .objective_short_history import validate_unchanged_events
from .puzzle_session_validate import legal_move


def completed(db, row, events, actions, index, event):
    result = verified(db, row, event)
    if result is None:
        return False
    if result["complete"]:
        return _immediate(row, actions, result)
    if len(actions) != 2 or row["status"] != "objective_verified":
        return False
    return _finish(row, events, actions[1], index, result)


def _immediate(row, actions, result):
    return (
        len(actions) == 1
        and row["status"] == "needs_verification"
        and row["current_fen"] == result["board"].fen()
    )


def _finish(row, events, final, index, result):
    final_index, final_event, final_detail = final
    board = result["board"]
    validate_unchanged_events(events[index + 1 : final_index], board.fen())
    if (
        final_detail.get("feedback") != "objective_verified"
        or final_detail.get("input_fen") != board.fen()
        or final_detail.get("opponent_before_move") != result["defense"]
    ):
        return False
    board.push(legal_move(board, final_event["submitted_move"]))
    return board.is_checkmate() and final_detail.get("fen") == row["current_fen"] == board.fen()
