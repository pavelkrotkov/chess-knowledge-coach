"""Record a continuation move or assistance without altering the original event."""

import json

from .objective_short_move import move_result
from .unified_session_state import now, session_row, view


def record(db, row, event_id, kind, move, continuation):
    if continuation["complete"]:
        raise ValueError("practice attempt is complete")
    board = continuation["board"]
    input_fen = board.fen()
    if kind == "hint":
        db.connection.execute(
            "UPDATE unified_sessions SET hints_used=hints_used+1 WHERE attempt_id=?",
            (row["attempt_id"],),
        )
        detail = _hint(move, continuation["mate"], input_fen)
    else:
        detail = move_result(board, move)
        if detail["feedback"] != "illegal":
            db.connection.execute(
                "UPDATE unified_sessions SET current_fen=?,status=?,finished_at=? WHERE attempt_id=?",
                (detail["fen"], detail["status"], now(), row["attempt_id"]),
            )
    result = (
        view(session_row(db, row["attempt_id"], row["subject"])) | detail | {"input_fen": input_fen}
    )
    if kind == "move" and detail["feedback"] != "illegal":
        result["opponent_before_move"] = continuation["defense"]
    db.connection.execute(
        "INSERT INTO unified_session_events VALUES(?,?,?,?,?,?)",
        (row["attempt_id"], event_id, kind, move, json.dumps(result, sort_keys=True), now()),
    )
    return result


def _hint(move, mate, fen):
    if move == "reveal":
        return {
            "feedback": "revealed",
            "revealed_line": mate,
            "assistance_kind": "revealed",
            "fen": fen,
        }
    return {"feedback": "hint", "hint": mate[:2], "assistance_kind": "hinted", "fen": fen}
