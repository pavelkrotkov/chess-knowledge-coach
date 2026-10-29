"""Apply and persist a single new practice event."""

import json

from .unified_session_moves import apply_move
from .unified_session_state import now, session_row, view


def record_event(db, row, event_id, kind, move):
    if row["status"] != "active":
        raise ValueError("practice attempt is not active")
    lines = json.loads(row["lines_json"])
    candidates = json.loads(row["candidates_json"])
    if kind == "hint":
        remaining = lines[candidates[0]][row["next_index"] :]
        square = remaining[0][:2]
        db.connection.execute(
            "UPDATE unified_sessions SET hints_used=hints_used+1 WHERE attempt_id=?",
            (row["attempt_id"],),
        )
        detail = (
            {"feedback": "revealed", "revealed_line": " ".join(remaining)}
            if move == "reveal"
            else {"feedback": "hint", "hint": square}
        )
    else:
        detail = apply_move(row, lines, candidates, move)
        _save_move(db, row, detail)
    result = view(session_row(db, row["attempt_id"], row["subject"])) | {
        key: value
        for key, value in detail.items()
        if key in {"feedback", "hint", "opponent_move", "revealed_line"}
    }
    db.connection.execute(
        "INSERT INTO unified_session_events VALUES(?,?,?,?,?,?)",
        (row["attempt_id"], event_id, kind, move, json.dumps(result, sort_keys=True), now()),
    )
    return result


def _save_move(db, row, detail):
    finished = now() if detail["status"] != "active" else None
    db.connection.execute(
        """UPDATE unified_sessions SET current_fen=?,status=?,next_index=?,
        candidates_json=?,finished_at=? WHERE attempt_id=?""",
        (
            detail["fen"],
            detail["status"],
            detail["next_index"],
            json.dumps(detail["candidates"]),
            finished,
            row["attempt_id"],
        ),
    )
