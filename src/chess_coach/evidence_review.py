"""Review evidence with explicit actors and an append-only decision history."""

from __future__ import annotations

from datetime import UTC, datetime

from .db import Database
from .evidence_review_details import inspect_evidence as inspect_evidence
from .evidence_review_effects import invalidate_changed_eligibility
from .evidence_review_state import evidence_row
from .evidence_review_state import list_evidence as list_evidence
from .mapping_transaction import mapping_transaction


def review_evidence(
    db: Database,
    evidence_id: int,
    *,
    decision: str,
    actor: str,
    rationale: str | None = None,
) -> dict:
    _validate_request(decision, actor, rationale)
    with mapping_transaction(db):
        row = evidence_row(db, evidence_id)
        if decision == "revoke" and row["review_decision"] is None and not row["human_validated"]:
            raise ValueError("unreviewed evidence has no decision to revoke")
        db.connection.execute(
            """INSERT INTO evidence_review_events (evidence_id, decision, actor, rationale, reviewed_at)
            VALUES (?, ?, ?, ?, ?)""",
            (evidence_id, decision, actor, rationale, datetime.now(UTC).isoformat()),
        )
        db.connection.execute(
            "UPDATE evidence_mappings SET human_validated = ? WHERE id = ?",
            (int(decision == "accept"), evidence_id),
        )
        invalidate_changed_eligibility(db, row, decision)
        return inspect_evidence(db, evidence_id)


def _validate_request(decision: str, actor: str, rationale: str | None) -> None:
    if decision not in {"accept", "reject", "revoke"}:
        raise ValueError("decision must be accept, reject, or revoke")
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("review actor must be nonempty")
    if rationale is not None and not isinstance(rationale, str):
        raise ValueError("rationale must be text or unknown")


def validate_evidence(db: Database, evidence_id: int, *, actor: str) -> None:
    """Accept evidence through the audited review path."""
    review_evidence(db, evidence_id, decision="accept", actor=actor)
