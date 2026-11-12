"""List bounded own-game sources without exposing their solutions."""

from .discovery_defense_contract import MAPPER, PRACTICE
from .discovery_material_contract import MAPPER as MATERIAL_MAPPER
from .discovery_material_contract import PRACTICE as MATERIAL_PRACTICE
from .learner_identity import normalize_identity


def material_candidates(db, subject):
    return _candidates(db, subject, MATERIAL_MAPPER, MATERIAL_PRACTICE)


def candidates(db, subject):
    return _candidates(db, subject, MAPPER, PRACTICE)


def _candidates(db, subject, mapper, version):
    identity = normalize_identity(subject)
    if not identity:
        return {"version": version, "candidates": []}
    rows = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=? AND r.status='active' AND e.outcome='failure'
        AND COALESCE((SELECT decision FROM evidence_review_events v WHERE v.evidence_id=e.id
        ORDER BY v.id DESC LIMIT 1),'') NOT IN ('reject','revoke') ORDER BY e.id DESC LIMIT 10""",
        (identity, mapper),
    ).fetchall()
    return {"version": version, "candidates": [{"key": str(row["id"])} for row in rows]}
