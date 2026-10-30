"""List a bounded prefix of owned created-fork source candidates."""

from .fork_defense_contract import FACT_TYPE, MAPPER
from .learner_identity import normalize_identity
from .objective_fork_avoidance_contract import VERSION


def candidates(db, subject):
    rows = db.connection.execute(
        """SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id
        WHERE e.subject=? AND r.producer=? AND r.status='active'
        AND e.skill='fork' AND e.operation='prevent' AND e.outcome='failure'
        AND COALESCE((SELECT decision FROM evidence_review_events v WHERE v.evidence_id=e.id ORDER BY v.id DESC LIMIT 1),'') NOT IN ('reject','revoke')
        AND EXISTS (SELECT 1 FROM evidence_fact_links l JOIN detector_facts f ON f.id=l.fact_id
            WHERE l.evidence_id=e.id AND f.fact_type=? AND CASE WHEN json_valid(f.payload_json)
            THEN json_extract(f.payload_json,'$.threat_origin')='created_by_played_move' ELSE 0 END)
        ORDER BY e.id DESC LIMIT 10""",
        (normalize_identity(subject), MAPPER, FACT_TYPE),
    ).fetchall()
    return {"candidates": [{"key": str(row["id"])} for row in rows], "version": VERSION}
