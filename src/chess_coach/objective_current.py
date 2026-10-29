"""Recheck the owned objective snapshot and event prefix."""

import json

from .learner_identity import normalize_identity
from .objective_contract import OBJECTIVE, VERSION
from .objective_events import prefix, prefix_hash
from .objective_short_source import OBJECTIVE as SHORT_OBJECTIVE
from .objective_short_source import VERSION as SHORT_VERSION
from .unified_source_current import require_current


def current(db, request):
    session = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE attempt_id=?", (request["attempt_id"],)
    ).fetchone()
    if session is None or normalize_identity(session["subject"]) != request["subject"]:
        raise ValueError("verification source unavailable")
    require_current(db, session)
    data = json.loads(session["provenance_json"])
    if not _matches(session, data, request):
        raise ValueError("verification source changed")
    events = prefix(db, request["attempt_id"], request["event_id"])
    if prefix_hash(events) != request["event_prefix_hash"]:
        raise ValueError("verification history changed")
    return session, events


def _matches(session, data, request):
    return _scope(session, request) and _binding(session, data, request)


def _scope(session, request):
    return (
        session["source_type"] == "own-game"
        and (session["source_version"], session["objective"])
        in {(VERSION, "mate_in_one"), (SHORT_VERSION, "mate_within_two")}
        and session["status"] == "needs_verification"
        and session["snapshot_hash"] == request["snapshot_hash"]
        and session["learner_color"] == request["learner_color"]
    )


def _binding(session, data, request):
    return (
        data.get("objective_version") == request["objective_version"]
        and (session["source_version"], data.get("objective_version"))
        in {(VERSION, OBJECTIVE), (SHORT_VERSION, SHORT_OBJECTIVE)}
        and data.get("history_mode") == request["history_mode"]
        and data.get("source_fingerprint") == request["source_hash"]
    )
