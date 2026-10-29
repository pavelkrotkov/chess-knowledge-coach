"""Recover an event's original board for idempotent notation parsing."""

import json

from .puzzle_session_state import _session
from .puzzle_session_validate import validate_line
from .unified_session_state import session_row


def unified_input_fen(db, attempt, subject, event, current):
    row = session_row(db, attempt, subject)
    return _input_fen(db, "unified_session_events", attempt, event, row["prompt_fen"], current)


def puzzle_input_fen(db, attempt, event, current):
    row = _session(db, attempt)
    prompt = validate_line(row["initial_fen"], row["solution"])
    return _input_fen(db, "puzzle_session_events", attempt, event, prompt, current)


def _input_fen(db, table, attempt, event, prompt, current):
    row = db.connection.execute(
        f"SELECT rowid FROM {table} WHERE attempt_id=? AND event_id=?", (attempt, event)
    ).fetchone()
    if row is None:
        return current
    prior = db.connection.execute(
        f"SELECT response_json FROM {table} WHERE attempt_id=? AND rowid<? ORDER BY rowid DESC LIMIT 1",
        (attempt, row[0]),
    ).fetchone()
    if prior is None:
        return prompt
    try:
        fen = json.loads(prior[0])["fen"]
    except (ValueError, TypeError, KeyError):
        raise ValueError("practice history unavailable") from None
    if not isinstance(fen, str):
        raise ValueError("practice history unavailable")
    return fen
