"""Build one shared, bounded explanation from eligible learner evidence."""

from datetime import datetime

from .db import Database
from .mastery_eligibility import eligible_contexts
from .mastery_policy import calculate


def evidence_summary(db: Database, subject: str, now: datetime, scan_limit: int) -> dict:
    rows = db.connection.execute(
        """SELECT id FROM evidence_mappings INDEXED BY idx_curriculum_evidence
        WHERE subject=? AND skill='mate_in_one' AND operation='execute' ORDER BY id LIMIT ?""",
        (subject, scan_limit + 1),
    ).fetchall()
    if len(rows) > scan_limit:
        return {
            "ref": "mate_in_one",
            "state": "evidence_scan_incomplete",
            "context_count": None,
            "mastery": None,
            "supporting_evidence_ids": [],
            "exclusions": {},
            "weakness_threshold": 0.6,
            "source_rows_examined": scan_limit,
            "source_scan_incomplete": True,
        }
    contexts, exclusions = eligible_contexts(db, subject, "mate_in_one", "execute", now)
    values = calculate(contexts)
    if not rows:
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
        "source_rows_examined": len(rows),
        "source_scan_incomplete": False,
    }
