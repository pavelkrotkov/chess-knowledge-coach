"""Create and recheck one immutable, objective-bound verification request."""

import json

from .learner_identity import normalize_identity
from .objective_binding_scope import owned_source
from .objective_events import prefix, prefix_hash
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .related_capture_objective import is_source as capture_assessment
from .related_fork_assessment_scope import is_source as fork_assessment
from .unified_session_state import now


def enqueue(db, session, event_id, result):
    if not _supported(session):
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


def _supported(session):
    if session["source_type"] == "public":
        return session["objective"] in PROMOTION_OBJECTIVES
    return capture_assessment(session) or fork_assessment(session) or owned_source(session)
