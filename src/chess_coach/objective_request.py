"""Create and recheck one immutable, objective-bound verification request."""

import json

from .learner_identity import normalize_identity
from .objective_capture_contract import VERSIONS as CAPTURE_VERSIONS
from .objective_contract import VERSION
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_events import prefix, prefix_hash
from .objective_short_source import VERSION as SHORT_VERSION
from .unified_session_state import now


def enqueue(db, session, event_id, result):
    if session["source_type"] != "own-game" or session["source_version"] not in {
        *CAPTURE_VERSIONS,
        VERSION,
        SHORT_VERSION,
        DEFENSE_VERSION,
    }:
        return
    if result.get("feedback") != "needs_verification":
        return
    data = json.loads(session["provenance_json"])
    try:
        events = prefix(db, session["attempt_id"], event_id)
        event_hash = prefix_hash(events)
    except ValueError:
        event_hash = "unavailable"
    db.connection.execute(
        """INSERT INTO objective_requests
        (attempt_id,event_id,subject,objective_version,history_mode,snapshot_hash,source_hash,
         event_prefix_hash,learner_color,requested_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            session["attempt_id"],
            event_id,
            normalize_identity(session["subject"]),
            data["objective_version"],
            data["history_mode"],
            session["snapshot_hash"],
            data["source_fingerprint"],
            event_hash,
            session["learner_color"],
            now(),
        ),
    )
