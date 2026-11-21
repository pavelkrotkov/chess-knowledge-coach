"""Read learning receipts and retry a committed terminal attempt."""

import json
import sqlite3
from contextlib import suppress

from .mastery_time import parse_utc


def status(db, attempt_id):
    if db.compat32:
        return None
    row = db.connection.execute(
        """SELECT e.item_id,c.response_json,s.status,s.finished_at,s.hints_used,i.last_review
        FROM unified_training_enrollments e
        JOIN unified_sessions s ON s.attempt_id=e.attempt_id
        JOIN training_items i ON i.id=e.item_id
        LEFT JOIN unified_training_completions c ON c.attempt_id=e.attempt_id WHERE e.attempt_id=?""",
        (attempt_id,),
    ).fetchone()
    if row is None:
        return None
    if row["response_json"] is None:
        return {
            "state": _pending_state(row),
            "item_id": row["item_id"],
        }
    return {"state": "completed", **json.loads(row["response_json"])}


def _pending_state(row):
    if row["status"] == "active":
        return "in_progress"
    answered = parse_utc(row["finished_at"])
    reviewed = parse_utc(row["last_review"])
    if not row["hints_used"] and answered and reviewed and reviewed > answered:
        return "superseded"
    return "pending"


def finish(db, row, attempt_id, subject, event_id, result):
    if row["source_type"] != "corpus":
        return result
    current = status(db, attempt_id)
    if current is None or result["status"] not in ("objective_verified", "line_completed"):
        return result
    from .unified_training_complete import complete

    # The accepted move remains durable; explicit retry is available.
    with suppress(ValueError, sqlite3.Error, RuntimeError, OverflowError):
        complete(db, attempt_id, subject, event_id=event_id)
    return {**result, "learning": status(db, attempt_id)}


def for_show(db, row, result):
    learning = status(db, row["attempt_id"])
    if row["source_type"] == "corpus" or learning is not None:
        result["learning"] = learning
    if learning and learning["state"] == "completed":
        result["source_key"] = row["source_key"]
    if learning and result.get("verification", {}).get("status") == "unresolved":
        learning["state"] = "unresolved"
