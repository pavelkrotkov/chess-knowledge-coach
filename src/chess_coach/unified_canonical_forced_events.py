"""Validate actual events after the deterministic forced-promotion reply."""

from .objective_events import response


def final(event, board, actual_reply, row):
    detail = response(event)
    if event["kind"] != "move" or detail.get("input_fen") != board.fen():
        raise ValueError("forced promotion final answer unavailable")
    if detail.get("opponent_before_move") != actual_reply:
        raise ValueError("forced promotion reply changed")
    move = board.parse_uci(event["submitted_move"])
    if not move or move not in board.legal_moves:
        raise ValueError("forced promotion final move unavailable")
    board.push(move)
    if not _matches(row, detail, board.fen(), bool(move.promotion)) or not row["finished_at"]:
        raise ValueError("forced promotion final position changed")
    return _status(move.promotion), move.uci()


def _matches(row, detail, fen, promoted):
    status = "objective_verified" if promoted else "line_completed"
    feedback = "objective_verified" if promoted else "incorrect"
    return (
        row["status"],
        row["current_fen"],
        detail.get("status"),
        detail.get("fen"),
        detail.get("feedback"),
    ) == (status, fen, status, fen, feedback)


def _status(promoted):
    return "correct" if promoted else "incorrect"
