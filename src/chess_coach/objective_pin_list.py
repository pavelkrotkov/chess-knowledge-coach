"""List bounded subject-owned pin references, checked again on admission."""

from .learner_identity import normalize_identity
from .objective_pin_contract import VERSION


def candidates(db, subject):
    rows = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer='pin-execute-mapper' AND r.status='active'
        AND e.skill IN ('absolute_pin','relative_pin') AND e.operation='execute'
        AND e.outcome='success'
        AND COALESCE((SELECT decision FROM evidence_review_events v WHERE v.evidence_id=e.id ORDER BY v.id DESC LIMIT 1),'') NOT IN ('reject','revoke')
        ORDER BY e.id DESC LIMIT 10""",
        (normalize_identity(subject),),
    ).fetchall()
    return {"candidates": [{"key": str(row["id"])} for row in rows], "version": VERSION}
