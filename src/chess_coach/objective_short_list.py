"""List a bounded set of owned short-mate source references."""

from .learner_identity import normalize_identity
from .mate_contract import MAPPER
from .objective_short_source import VERSION


def candidates(db, subject):
    identity = normalize_identity(subject)
    if not identity:
        return {"version": VERSION, "candidates": []}
    rows = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=? AND r.status=\u0027active\u0027
        AND e.skill=\u0027calculation\u0027 AND e.operation=\u0027execute\u0027
        AND COALESCE((SELECT decision FROM evidence_review_events v WHERE v.evidence_id=e.id ORDER BY v.id DESC LIMIT 1),\u0027\u0027) NOT IN (\u0027reject\u0027,\u0027revoke\u0027)
        ORDER BY e.id DESC LIMIT 10""",
        (identity, MAPPER),
    ).fetchall()
    return {"version": VERSION, "candidates": [{"key": str(row["id"])} for row in rows]}
