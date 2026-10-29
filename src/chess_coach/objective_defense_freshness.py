"""Recheck the source after bounded exemplar verification."""

from .back_rank_evidence import load
from .objective_defense_policy import eligible


def review_id(db, evidence_id):
    row = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence_id,),
    ).fetchone()
    return row["id"] if row else None


def require_unchanged(db, subject, evidence, fact, fingerprint, review):
    current, current_fact, current_fingerprint = load(db, evidence["id"], subject)
    fields = (
        "subject",
        "operation",
        "position_id",
        "mapping_run_id",
        "review_status",
        "mapper_version",
    )
    if any(current[field] != evidence[field] for field in fields):
        raise ValueError("defense source changed")
    if (
        not eligible(db, current, current_fact)
        or current_fact["detector_run_id"] != fact["detector_run_id"]
    ):
        raise ValueError("defense source changed")
    if current_fingerprint != fingerprint or review_id(db, evidence["id"]) != review:
        raise ValueError("defense source changed")
