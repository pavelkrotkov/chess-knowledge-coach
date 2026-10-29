"""Replay unchanged fork observations without repeating bounded chess proofs."""

import json

from .fork_contract import MAPPER, PRODUCER, VERSION
from .material_replay import source_inputs


def current_result(db, prepared):
    row = db.connection.execute(
        "SELECT id,input_json FROM detector_runs WHERE position_id=? AND producer=? AND detector_version=? AND status=?",
        (prepared["position_id"], PRODUCER, VERSION, "active"),
    ).fetchone()
    if row is None or not _same_inputs(row, prepared):
        return None
    facts = db.connection.execute(
        "SELECT id,fact_type,detector_version FROM detector_facts WHERE run_id=?", (row["id"],)
    ).fetchall()
    if not facts:
        return {
            "detector_run_id": row["id"],
            "fact_ids": [],
            "mapping_run_id": None,
            "evidence_ids": [],
            "replayed": True,
            "outcome": "no_opportunity",
        }
    if (
        len(facts) != 1
        or facts[0]["fact_type"] != "fork_opportunity"
        or facts[0]["detector_version"] != VERSION
    ):
        return None
    return _mapping(db, prepared, row["id"], facts[0]["id"])


def _same_inputs(row, prepared):
    try:
        prior = json.loads(row["input_json"])["detector_input"]
        return {
            key: value for key, value in prior.items() if key != "reactivation"
        } == source_inputs(prepared)
    except (TypeError, ValueError, KeyError, AttributeError):
        return False


def _mapping(db, prepared, run_id, fact_id):
    row = db.connection.execute(
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
            fact_id,
        ),
    ).fetchone()
    if row is None:
        return None
    return {
        "detector_run_id": run_id,
        "fact_ids": [fact_id],
        "mapping_run_id": row["mapping_run_id"],
        "evidence_ids": [row["id"]],
        "replayed": True,
        "outcome": row["outcome"],
    }
