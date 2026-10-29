"""Validate current, versioned back-rank detector output and its mappings."""

import json

from .back_rank_contract import FACT_TYPE, MAPPER, PRODUCER, VERSION
from .back_rank_outcomes import outcomes, status
from .fact_inputs import fact_batch


def replay(db, position_id, key, subject):
    row = db.connection.execute(
        """SELECT d.id,d.input_json,d.output_hash,f.id AS fact_id,f.fact_key,f.payload_json
        FROM detector_runs d JOIN detector_facts f ON f.run_id=d.id
        WHERE d.position_id=? AND d.producer=? AND d.detector_version=? AND d.status='active'
        AND f.fact_type=?""",
        (position_id, PRODUCER, VERSION, FACT_TYPE),
    ).fetchone()
    if row is None:
        return None
    try:
        prior = json.loads(row["input_json"])["detector_input"]
        fact = json.loads(row["payload_json"])
        items, output_hash = fact_batch([{"fact_type": FACT_TYPE, "payload": fact}])
    except (ValueError, TypeError, KeyError):
        raise ValueError("stored back-rank output is invalid") from None
    if prior.get("source_fingerprint") != key:
        return None
    if items[0][0] != row["fact_key"] or output_hash != row["output_hash"]:
        raise ValueError("stored back-rank output is invalid")
    for operation, _ in outcomes(fact):
        if not _has_mapping(db, row["fact_id"], subject, operation):
            raise ValueError("stored back-rank mapping unavailable")
    return {"replayed": True, "run_id": row["id"], "observation_status": status(fact)}


def _has_mapping(db, fact_id, subject, operation):
    row = db.connection.execute(
        """SELECT COUNT(*) FROM evidence_fact_links l JOIN evidence_mappings e ON e.id=l.evidence_id
        JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE l.fact_id=? AND l.active=1
        AND l.subject=? AND l.operation=? AND l.skill='back_rank'
        AND e.subject=? AND e.operation=? AND e.skill='back_rank' AND e.mapper_version=?
        AND r.subject=? AND r.operation=? AND r.producer=? AND r.mapper_version=? AND r.status='active'""",
        (
            fact_id,
            subject,
            operation,
            subject,
            operation,
            VERSION,
            subject,
            operation,
            MAPPER,
            VERSION,
        ),
    ).fetchone()
    return row[0] == 1
