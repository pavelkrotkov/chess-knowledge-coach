"""Persist and reactivate versioned material fact lineage."""

import json

from .fact_runs import record_fact_run_in_transaction
from .material_contract import PRODUCER, VERSION


def fact_run(db, position_id, inputs, fact):
    active = db.connection.execute(
        "SELECT id,input_json FROM detector_runs WHERE position_id=? AND producer=? AND status=?",
        (position_id, PRODUCER, "active"),
    ).fetchone()
    if active:
        prior = json.loads(active["input_json"])["detector_input"]
        if {key: value for key, value in prior.items() if key != "reactivation"} == inputs:
            inputs = prior
    facts = [] if fact is None else [{"fact_type": "material_opportunity", "payload": fact}]
    run = record_fact_run_in_transaction(
        db,
        position_id=position_id,
        producer=PRODUCER,
        detector_version=VERSION,
        input_data=inputs,
        facts=facts,
    )
    if run["status"] != "active":
        latest = db.connection.execute(
            "SELECT MAX(id) FROM detector_runs WHERE position_id=? AND producer=?",
            (position_id, PRODUCER),
        ).fetchone()[0]
        run = record_fact_run_in_transaction(
            db,
            position_id=position_id,
            producer=PRODUCER,
            detector_version=VERSION,
            input_data={**inputs, "reactivation": latest},
            facts=facts,
        )
    return run
