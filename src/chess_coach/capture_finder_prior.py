"""Resolve the exact current unassisted prior assessment for a matching search."""

import json

from .capture_compare_scope import scope
from .capture_plan_history import latest


def prior(db, subject, corpus, attempt, check):
    if not isinstance(attempt, str) or not attempt or len(attempt) > 128 or not attempt.isascii():
        raise ValueError("assessment unavailable")
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE subject=? AND attempt_id=?", (subject, attempt)
    ).fetchone()
    if row is None:
        raise ValueError("assessment unavailable")
    matched = scope(row, corpus)
    if matched is None:
        raise ValueError("assessment context unavailable")
    position = json.loads(row["provenance_json"])["related_capture"]["position_id"]
    check()
    history = latest(db, subject, position, corpus, check=check)
    if (history.get("attempt_id"), history.get("status"), history.get("assistance")) != (
        attempt,
        "correct",
        "unassisted",
    ):
        raise ValueError("assessment is not a current unassisted correct result")
    check()
    return position, matched["key"]


def prepare(db, subject, corpus, attempt, position, deadline, expired):
    if attempt is None:
        return position, None

    def check():
        if expired(deadline):
            raise ValueError("capture finder deadline")

    previous, expected = prior(db, subject, corpus, attempt, check)
    if position is not None and position != previous:
        raise ValueError("capture source changed")
    return previous, expected
