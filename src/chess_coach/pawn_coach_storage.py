"""Publish immutable pawn facts without transferring historical reviews."""

import json

from .fact_runs import record_fact_run_in_transaction
from .pawn_coach_contract import FACT_TYPE, PRODUCER, VERSION


def fact_run(db, prepared):
    position_id, inputs, fact = prepared["position"]["id"], prepared["inputs"], prepared["fact"]
    active = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE position_id=? AND producer=? AND status='active'",
        (position_id, PRODUCER),
    ).fetchone()
    if active:
        prior = json.loads(active["input_json"])["detector_input"]
        if {k: v for k, v in prior.items() if k != "reactivation"} == inputs:
            inputs = prior
    facts = [] if fact is None else [{"fact_type": FACT_TYPE, "payload": fact}]
    result = _record(db, position_id, inputs, facts)
    if result["status"] != "active":
        latest = db.connection.execute(
            "SELECT MAX(id) FROM detector_runs WHERE position_id=? AND producer=?",
            (position_id, PRODUCER),
        ).fetchone()[0]
        result = _record(db, position_id, {**inputs, "reactivation": latest}, facts)
    return result


def _record(db, position_id, inputs, facts):
    return record_fact_run_in_transaction(
        db,
        position_id=position_id,
        producer=PRODUCER,
        detector_version=VERSION,
        input_data=inputs,
        facts=facts,
    )
