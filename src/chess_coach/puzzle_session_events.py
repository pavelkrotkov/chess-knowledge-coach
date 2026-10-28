"""Apply learner events once and persist their responses atomically."""

from __future__ import annotations

import json

from .db import Database
from .puzzle_session_apply import _record_event
from .puzzle_session_state import _session


def submit_move(db: Database, attempt_id: str, *, event_id: str, move: str) -> dict[str, object]:
    if not isinstance(move, str):
        raise ValueError("move must be UCI text")
    return _apply_event(db, attempt_id, event_id, "move", move)


def request_hint(db: Database, attempt_id: str, *, event_id: str) -> dict[str, object]:
    return _apply_event(db, attempt_id, event_id, "hint", None)


def _apply_event(
    db: Database, attempt_id: str, event_id: str, kind: str, move: str | None
) -> dict[str, object]:
    if not event_id:
        raise ValueError("event ID is required")
    if db.connection.in_transaction:
        raise RuntimeError("cannot submit an event during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        result = apply_event_in_transaction(db, attempt_id, event_id, kind, move)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def apply_event_in_transaction(
    db: Database, attempt_id: str, event_id: str, kind: str, move: str | None
) -> dict[str, object]:
    """Apply an idempotent event without committing the caller's transaction."""
    if not db.connection.in_transaction:
        raise RuntimeError("puzzle event requires a transaction")
    if not event_id:
        raise ValueError("event ID is required")
    row = _session(db, attempt_id)
    previous = db.connection.execute(
        "SELECT kind, submitted_move, response_json FROM puzzle_session_events "
        "WHERE attempt_id = ? AND event_id = ?",
        (attempt_id, event_id),
    ).fetchone()
    if previous is not None:
        if previous["kind"] != kind or previous["submitted_move"] != move:
            raise ValueError("event ID already used for a different request")
        return json.loads(previous["response_json"])
    return _record_event(db, row, event_id, kind, move)
