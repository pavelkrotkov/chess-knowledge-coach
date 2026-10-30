"""Queue the next legal pawn turn without rewriting earlier proof events."""

import json

from .puzzle_session_validate import legal_move
from .unified_session_state import now, session_row, view


def record(db, row, event_id, kind, text, resumed):
    if kind != "move":
        raise ValueError("continuation hints are unavailable")
    board = resumed["board"]
    input_fen = board.fen()
    try:
        move = legal_move(board, text)
    except ValueError:
        detail = {"feedback": "illegal", "status": "needs_verification", "fen": input_fen}
    else:
        board.push(move)
        detail = {
            "feedback": "needs_verification",
            "status": "needs_verification",
            "fen": board.fen(),
        }
        db.connection.execute(
            "UPDATE unified_sessions SET current_fen=?,status=?,finished_at=? WHERE attempt_id=?",
            (detail["fen"], detail["status"], now(), row["attempt_id"]),
        )
    result = (
        view(session_row(db, row["attempt_id"], row["subject"])) | detail | {"input_fen": input_fen}
    )
    if detail["feedback"] != "illegal":
        result["opponent_before_move"] = resumed["reply"]
    db.connection.execute(
        "INSERT INTO unified_session_events VALUES(?,?,?,?,?,?)",
        (row["attempt_id"], event_id, kind, text, json.dumps(result, sort_keys=True), now()),
    )
    return result
