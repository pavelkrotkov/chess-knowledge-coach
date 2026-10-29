"""List bounded references for the two explicit capture objectives."""

from .learner_identity import normalize_identity
from .material_policy import MAPPER
from .objective_capture_contract import GAIN_VERSION, TARGET_VERSION


def candidates(db, subject):
    identity = normalize_identity(subject)
    if not identity:
        return {"candidates": [], "target_version": TARGET_VERSION, "gain_version": GAIN_VERSION}
    rows = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=? AND r.status=\u0027active\u0027
        AND e.skill=\u0027hanging_piece\u0027 AND e.operation=\u0027execute\u0027
        AND COALESCE((SELECT decision FROM evidence_review_events v WHERE v.evidence_id=e.id ORDER BY v.id DESC LIMIT 1),\u0027\u0027) NOT IN (\u0027reject\u0027,\u0027revoke\u0027)
        ORDER BY e.id DESC LIMIT 10""",
        (identity, MAPPER),
    ).fetchall()
    return {
        "candidates": [{"key": str(row["id"])} for row in rows],
        "target_version": TARGET_VERSION,
        "gain_version": GAIN_VERSION,
    }
