"""Recognize an unchanged active material decision without rerunning verification."""

import json

from .material_contract import PRODUCER, VERSION
from .material_policy import MAPPER


def source_inputs(prepared):
    context = prepared["context"]
    return {
        "source_marker": prepared["source_marker"],
        "provenance": prepared["provenance"],
        "pre_move_fen": context["pre_move_fen"],
        "played_move": context["played_move"],
    }


def current_result(db, prepared):
    row = db.connection.execute(
        """SELECT id,input_json FROM detector_runs WHERE position_id=? AND producer=?
        AND detector_version=? AND status=?""",
        (prepared["position_id"], PRODUCER, VERSION, "active"),
    ).fetchone()
    if row is None:
        return None
    try:
        prior = json.loads(row["input_json"])["detector_input"]
    except (TypeError, ValueError, KeyError):
        return None
    if {key: value for key, value in prior.items() if key != "reactivation"} != source_inputs(
        prepared
    ):
        return None
    facts = db.connection.execute(
        "SELECT id,payload_json FROM detector_facts WHERE run_id=?", (row["id"],)
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
    if len(facts) != 1:
        return None
    return _mapped_result(db, prepared, row["id"], facts[0])


def _mapped_result(db, prepared, run_id, fact):
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
