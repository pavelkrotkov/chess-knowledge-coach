"""Recheck the owned objective snapshot and event prefix."""

import json

from .learner_identity import normalize_identity
from .objective_binding import matches, matches_short_terminal
from .objective_events import prefix, prefix_hash
from .unified_source_current import require_current


def current(db, request, *, related_cache=None):
    return _current(db, request, matches, related_cache)


def short_terminal(db, request):
    return _current(db, request, matches_short_terminal)


def _current(db, request, binding, related_cache=None):
    session = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE attempt_id=?", (request["attempt_id"],)
    ).fetchone()
    if session is None or normalize_identity(session["subject"]) != request["subject"]:
        raise ValueError("verification source unavailable")
    data = json.loads(session["provenance_json"])
    if not binding(session, data, request):
        raise ValueError("verification source changed")
    require_current(db, session, related_cache=related_cache)
    events = prefix(db, request["attempt_id"], request["event_id"])
    if prefix_hash(events) != request["event_prefix_hash"]:
        raise ValueError("verification history changed")
    return session, events
