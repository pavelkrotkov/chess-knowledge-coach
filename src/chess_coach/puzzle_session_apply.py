"""Apply and store one new puzzle attempt event."""

from __future__ import annotations

import json
from sqlite3 import Row

from .db import Database
from .puzzle_session_rules import apply_move, hint_square
from .puzzle_session_state import _now, _session, _view


def _record_event(
    db: Database, row: Row, event_id: str, kind: str, move: str | None
) -> dict[str, object]:
    if row["status"] != "active":
        raise ValueError("puzzle attempt is already complete")
    now = _now()
    if kind == "hint":
        detail: dict[str, object] = {
            "feedback": "hint",
            "hint": hint_square(row["solution"], row["next_index"]),
        }
        db.connection.execute(
            "UPDATE puzzle_sessions SET hints_used = hints_used + 1 WHERE attempt_id = ?",
            (row["attempt_id"],),
        )
    else:
        assert move is not None
        decision = apply_move(row["current_fen"], row["solution"], row["next_index"], move)
        finished_at = now if decision["status"] != "active" else None
        db.connection.execute(
            """UPDATE puzzle_sessions SET current_fen = ?, next_index = ?, status = ?, finished_at = ?
            WHERE attempt_id = ?""",
            (
                decision["fen"],
                decision["next_index"],
                decision["status"],
                finished_at,
                row["attempt_id"],
            ),
        )
        detail = {"feedback": decision["feedback"], "opponent_move": decision.get("opponent_move")}
    result = _view(_session(db, row["attempt_id"])) | detail
    db.connection.execute(
        """INSERT INTO puzzle_session_events
        (attempt_id, event_id, kind, submitted_move, response_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (row["attempt_id"], event_id, kind, move, json.dumps(result, sort_keys=True), now),
    )
    return result
