"""List bounded owned fork evidence references for explicit practice."""

from .fork_contract import MAPPER
from .learner_identity import normalize_identity
from .objective_fork_contract import VERSION


def candidates(db, subject):
    identity = normalize_identity(subject)
    rows = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=? AND r.status='active'
        AND e.skill='fork' AND e.operation='execute'
        AND COALESCE((SELECT decision FROM evidence_review_events v WHERE v.evidence_id=e.id ORDER BY v.id DESC LIMIT 1),'') NOT IN ('reject','revoke')
        ORDER BY e.id DESC LIMIT 10""",
        (identity, MAPPER),
    ).fetchall()
    return {"candidates": [{"key": str(row["id"])} for row in rows], "version": VERSION}
