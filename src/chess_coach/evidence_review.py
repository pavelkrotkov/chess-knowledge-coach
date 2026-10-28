"""Validate evidence and invalidate mastery only when eligibility changes."""

from .db import Database


def validate_evidence(db: Database, evidence_id: int) -> None:
    row = db.connection.execute(
        """SELECT e.human_validated, e.mapping_run_id, r.status
        FROM evidence_mappings e LEFT JOIN mapping_runs r ON r.id = e.mapping_run_id
        WHERE e.id = ?""",
        (evidence_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown evidence mapping: {evidence_id}")
    if row["human_validated"]:
        return
    db.connection.execute(
        "UPDATE evidence_mappings SET human_validated = 1 WHERE id = ?", (evidence_id,)
    )
    if row["mapping_run_id"] is None or row["status"] == "active":
        db.connection.execute(
            """UPDATE mastery_states SET is_stale = 1 WHERE (subject, skill, operation) IN
            (SELECT subject, skill, operation FROM evidence_mappings WHERE id = ?)""",
            (evidence_id,),
        )
    db.connection.commit()
