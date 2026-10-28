"""Build one shared, read-only explanation from eligible learner evidence."""

from datetime import datetime

from .db import Database
from .mastery_eligibility import eligible_contexts
from .mastery_policy import calculate


def evidence_summary(db: Database, subject: str, now: datetime) -> dict:
    contexts, exclusions = eligible_contexts(db, subject, "mate_in_one", "execute", now)
    values = calculate(contexts)
    raw = db.connection.execute(
        """SELECT COUNT(*) FROM evidence_mappings
        WHERE subject=? AND skill='mate_in_one' AND operation='execute'""",
        (subject,),
    ).fetchone()[0]
    if raw == 0:
        state = "cold_start"
    elif values["status"] == "insufficient":
        state = "insufficient_evidence"
    elif values["mastery"] < 0.6:
        state = "supported_weakness"
    else:
        state = "no_supported_weakness"
    return {
        "ref": "mate_in_one",
        "state": state,
        "context_count": values["context_count"],
        "mastery": values["mastery"],
        "supporting_evidence_ids": values["supporting_evidence_ids"],
        "exclusions": exclusions,
        "weakness_threshold": 0.6,
    }
