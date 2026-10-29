"""Read current back-rank coverage without performing another proof."""

import json

from .back_rank_contract import FACT_TYPE, MAPPER
from .back_rank_inputs import inputs
from .back_rank_replay import replay
from .learner_identity import normalize_identity
from .mate_inspection_source import position_row


def automatic_view(db, position_id, learner):
    try:
        position = position_row(db, position_id)
        _, key, _ = inputs(db, position, learner)
        current = replay(db, position_id, key, normalize_identity(learner))
        if not current:
            return {"status": "not_processed_or_stale"}
        row = db.connection.execute(
            "SELECT payload_json FROM detector_facts WHERE run_id=? AND fact_type=?",
            (current["run_id"], FACT_TYPE),
        ).fetchone()
        evidence = db.connection.execute(
            """SELECT e.id,e.operation FROM evidence_mappings e
            JOIN mapping_runs r ON r.id=e.mapping_run_id
            JOIN evidence_fact_links l ON l.evidence_id=e.id
            JOIN detector_facts f ON f.id=l.fact_id
            WHERE f.run_id=? AND e.subject=? AND l.active=1 AND r.producer=? AND r.status='active'
            ORDER BY e.id""",
            (current["run_id"], normalize_identity(learner), MAPPER),
        ).fetchall()
        return {
            "status": current["observation_status"],
            "observation": json.loads(row[0]),
            "evidence": [dict(item) for item in evidence],
        }
    except (ValueError, TypeError, KeyError):
        return {"status": "unavailable"}
