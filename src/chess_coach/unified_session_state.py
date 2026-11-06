"""Load subject-owned attempts and expose only non-solution session state."""

from datetime import UTC, datetime

from .related_backrank_view import add_fields as add_backrank_fields
from .related_fork_prevention_view import add_fields as add_prevention_fields
from .related_protection_view import add_fields as add_protection_fields
from .unified_owned_view import add_fields as add_owned_fields
from .unified_public_outcome import direct as direct_public
from .unified_public_outcome import outcome as public_outcome
from .unified_session_recent import recent as recent


def now():
    return datetime.now(UTC).isoformat()


def session_row(db, attempt_id, subject):
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE attempt_id=? AND subject=?", (attempt_id, subject)
    ).fetchone()
    if row is None:
        raise ValueError("unknown practice attempt")
    return row


def view(row):
    result = {
        "attempt_id": row["attempt_id"],
        "source_type": row["source_type"],
        "source_version": row["source_version"],
        "source_key": row["source_key"],
        "fen": row["current_fen"],
        "learner_color": row["learner_color"],
        "objective": row["objective"],
        "status": row["status"],
        "hints_used": row["hints_used"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }
    if row["status"] in {"active", "needs_verification"}:
        result.pop("source_key")
    public = public_outcome(row)
    if public is not None:
        result["public_outcome"] = public
        result["status"] = public
        if direct_public(row):
            result["source_key"] = row["source_key"]
    if row["source_type"] == "corpus":
        import json

        from .related_capture_objective import is_source as capture_assessment

        if capture_assessment(row):
            provenance = json.loads(row["provenance_json"])
            result["capture_assessment"] = True
            result["objective_target"] = provenance["objective_target"]
            result["gain_threshold"] = provenance["gain_threshold"]

        result["short_mate_assessment"] = bool(
            json.loads(row["provenance_json"]).get("related_mate", {}).get("assessment")
        )
    if row["source_type"] == "own-game":
        add_owned_fields(result, row)
    add_protection_fields(result, row)
    add_prevention_fields(result, row)
    add_backrank_fields(result, row)
    return result
