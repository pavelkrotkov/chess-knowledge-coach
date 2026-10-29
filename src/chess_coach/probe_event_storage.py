"""Persist a single answer or assistance event."""

import json
from datetime import datetime

from .probe_grading import response
from .unified_session_state import now


def record(db, row, task, event_id, kind, answer, request):
    events = db.connection.execute(
        "SELECT kind FROM diagnostic_probe_events WHERE attempt_id=? ORDER BY rowid",
        (row["attempt_id"],),
    ).fetchall()
    if any(item["kind"] == "answer" for item in events) and kind == "answer":
        raise ValueError("probe already answered")
    timestamp = now()
    elapsed = (
        datetime.fromisoformat(timestamp) - datetime.fromisoformat(row["started_at"])
    ).total_seconds()
    elapsed = int(elapsed) if elapsed >= 0 else None
    assisted = any(item["kind"] in {"hint", "reveal"} for item in events)
    result = response(task, kind, answer, elapsed, assisted)
    db.connection.execute(
        "INSERT INTO diagnostic_probe_events VALUES (?,?,?,?,?,?)",
        (
            row["attempt_id"],
            event_id,
            kind,
            request,
            json.dumps(result, sort_keys=True),
            timestamp,
        ),
    )
    return result
