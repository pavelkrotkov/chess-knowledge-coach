"""Validate replay version and find its active mapping."""

import json

from .material_contract import VERSION, detector_version
from .material_policy import MAPPER


def mapped_result(db, prepared, run_id, fact):
    evidence = db.connection.execute(
        """SELECT e.id,e.outcome,e.mapping_run_id FROM evidence_mappings e
        JOIN mapping_runs r ON r.id=e.mapping_run_id JOIN evidence_fact_links l ON l.evidence_id=e.id
        WHERE r.producer=? AND r.mapper_version=? AND r.status=? AND e.subject=? AND e.position_id=?
          AND l.fact_id=? AND l.active=1""",
        (
            MAPPER,
            VERSION,
            "active",
            prepared["context"]["subject"],
            prepared["position_id"],
            fact["id"],
        ),
    ).fetchone()
    if evidence is None:
        return None
    return {
        "detector_run_id": run_id,
        "fact_ids": [fact["id"]],
        "mapping_run_id": evidence["mapping_run_id"],
        "evidence_ids": [evidence["id"]],
        "replayed": True,
        "outcome": evidence["outcome"],
    }


def current_version(row, facts):
    if len(facts) > 1:
        return False
    try:
        fact = json.loads(facts[0]["payload_json"]) if facts else None
        if facts and not isinstance(fact, dict):
            return False
        return row["detector_version"] == detector_version(fact)
    except (TypeError, ValueError):
        return False
