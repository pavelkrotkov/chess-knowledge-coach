"""Record the final promoting move or assistance without rewriting the proof."""

import json

from .puzzle_session_validate import legal_move
from .unified_session_state import now, session_row, view


def record(db, row, event_id, kind, text, resumed):
    if resumed["complete"]:
        raise ValueError("promotion attempt is complete")
    board = resumed["board"]
    input_fen = board.fen()
    if kind == "hint":
        db.connection.execute(
            "UPDATE unified_sessions SET hints_used=hints_used+1 WHERE attempt_id=?",
            (row["attempt_id"],),
        )
        detail = _hint(text, resumed["promotion"], input_fen)
    else:
        detail = _move(board, text)
        if detail["feedback"] != "illegal":
            db.connection.execute(
                "UPDATE unified_sessions SET current_fen=?,status=?,finished_at=? WHERE attempt_id=?",
                (detail["fen"], detail["status"], now(), row["attempt_id"]),
            )
    result = (
        view(session_row(db, row["attempt_id"], row["subject"])) | detail | {"input_fen": input_fen}
    )
    if kind == "move" and detail["feedback"] != "illegal":
        result["opponent_before_move"] = resumed["reply"]
    db.connection.execute(
        "INSERT INTO unified_session_events VALUES(?,?,?,?,?,?)",
        (row["attempt_id"], event_id, kind, text, json.dumps(result, sort_keys=True), now()),
    )
    return result


def _hint(text, promotion, fen):
    if text == "reveal":
        return {
            "feedback": "revealed",
            "revealed_line": promotion,
            "assistance_kind": "revealed",
            "fen": fen,
        }
    return {"feedback": "hint", "hint": promotion[:2], "assistance_kind": "hinted", "fen": fen}


def _move(board, text):
    try:
        move = legal_move(board, text)
    except (ValueError, TypeError):
        return {"feedback": "illegal", "status": "needs_verification", "fen": board.fen()}
    board.push(move)
    status = "objective_verified" if move.promotion else "line_completed"
    return {
        "feedback": "objective_verified" if move.promotion else "incorrect",
        "status": status,
        "fen": board.fen(),
    }
