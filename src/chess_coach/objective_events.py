"""Bind a verification request to the immutable ordered session event prefix."""

import json

from .fact_fingerprint import canonical, digest

MAX_EVENTS = 256


def prefix(db, attempt, event):
    target = db.connection.execute(
        "SELECT rowid FROM unified_session_events WHERE attempt_id=? AND event_id=?",
        (attempt, event),
    ).fetchone()
    if target is None:
        raise ValueError("verification event unavailable")
    rows = db.connection.execute(
        """SELECT event_id,kind,submitted_move,response_json,created_at FROM unified_session_events
        WHERE attempt_id=? AND rowid<=? ORDER BY rowid LIMIT ?""",
        (attempt, target[0], MAX_EVENTS + 1),
    ).fetchall()
    if not rows or len(rows) > MAX_EVENTS or rows[-1]["event_id"] != event:
        raise ValueError("verification event prefix unavailable")
    return [dict(row) for row in rows]


def prefix_hash(rows):
    return digest(canonical(rows))


def response(event):
    try:
        value = json.loads(event["response_json"])
    except (TypeError, ValueError, KeyError):
        raise ValueError("verification event unavailable") from None
    if not isinstance(value, dict):
        raise ValueError("verification event unavailable")
    return value


def assistance(rows):
    kinds = [response(row).get("assistance_kind") for row in rows if row["kind"] == "hint"]
    if "revealed" in kinds:
        return "revealed"
    if kinds and any(kind != "hinted" for kind in kinds):
        return "assisted_unknown"
    return "hinted" if kinds else "unassisted"
