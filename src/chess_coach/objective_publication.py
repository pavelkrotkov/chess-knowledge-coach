"""Atomically publish or cancel immutable objective results."""

import json

from .learner_identity import normalize_identity
from .objective_current import current
from .objective_verify import unresolved
from .unified_session_state import now


def publish(db, request, result):
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        existing = _existing(db, request)
        if existing is not None:
            db.connection.commit()
            return existing
        try:
            current(db, request)
        except (ValueError, KeyError, TypeError, IndexError):
            result = unresolved(request, "source_unavailable")
        _insert(db, request, result)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def cancel(db, subject, attempt, event):
    request = db.connection.execute(
        "SELECT * FROM objective_requests WHERE subject=? AND attempt_id=? AND event_id=?",
        (normalize_identity(subject), attempt, event),
    ).fetchone()
    if request is None:
        raise ValueError("verification request unavailable")
    if db.connection.in_transaction:
        raise RuntimeError("verification cancellation requires an idle database")
    return _cancel(db, request)


def _cancel(db, request):
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        result = _existing(db, request)
        if result is None:
            result = unresolved(request, "cancelled")
            _insert(db, request, result)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def _existing(db, request):
    row = db.connection.execute(
        "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
        (request["attempt_id"], request["event_id"]),
    ).fetchone()
    return json.loads(row[0]) if row else None


def _insert(db, request, result):
    db.connection.execute(
        "INSERT INTO objective_results VALUES(?,?,?,?)",
        (request["attempt_id"], request["event_id"], json.dumps(result, sort_keys=True), now()),
    )
