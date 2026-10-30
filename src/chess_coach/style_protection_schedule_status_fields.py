"""Expose safe current proof metadata and recheck its purpose request."""

import json

from .purpose_view import show
from .style_protection_schedule_use import valid_request
from .style_schedule_view_state import view_state


def provenance(row):
    binding = json.loads(row["binding_json"])
    provenance = binding["provenance"]
    return {
        "source_state": "current",
        "evidence_id": binding["evidence_id"],
        "target": provenance["objective_target"],
        "review_status": provenance["review_status"],
        "review_event_id": provenance["review_event_id"],
        "source_contract": binding["source_contract"],
        "mapper": binding["mapper"],
        "mapper_version": binding["mapper_version"],
        "verifier": binding["verifier"],
        "history_mode": provenance["history_mode"],
        "source_fingerprint": provenance["source_fingerprint"],
    }


def request_state(db, learner, row, views):
    request_id = row["request_id"]
    if not _slot_bound(db, row, request_id):
        return {"state": "unknown", "detail": "request_binding_unavailable"}
    if request_id is None:
        return {}
    if not valid_request(db, learner, row, request_id):
        return {"state": "unknown", "detail": "request_binding_mismatch"}
    view = views.get(request_id) if views else None
    if view is None:
        view = show(db, request_id, learner)
    if view["source_state"] != "current":
        return {"state": "unknown", "detail": "purpose_source_stale"}
    return {"purpose_state": view_state(view)}


def _slot_bound(db, row, request_id):
    if row["slot_id"] is None:
        return True
    slot = db.connection.execute(
        "SELECT request_id FROM style_schedule_slots WHERE id=?", (row["slot_id"],)
    ).fetchone()
    return slot is not None and slot["request_id"] == request_id
