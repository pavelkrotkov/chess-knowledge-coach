"""Persist fork facts with replay-safe reactivation."""

import json

from .fact_runs import record_fact_run_in_transaction
from .fork_contract import PRODUCER, VERSION


def fact_run(
    db,
    position_id,
    inputs,
    fact,
    *,
    producer=PRODUCER,
    version=VERSION,
    fact_type="fork_opportunity",
):
    active = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE position_id=? AND producer=? AND status=?",
        (position_id, producer, "active"),
    ).fetchone()
    if active:
        prior = json.loads(active["input_json"])["detector_input"]
        if {key: value for key, value in prior.items() if key != "reactivation"} == inputs:
            inputs = prior
    facts = [] if fact is None else [{"fact_type": fact_type, "payload": fact}]
    result = record_fact_run_in_transaction(
        db,
        position_id=position_id,
        producer=producer,
        detector_version=version,
        input_data=inputs,
        facts=facts,
    )
    if result["status"] != "active":
        latest = db.connection.execute(
            "SELECT MAX(id) FROM detector_runs WHERE position_id=? AND producer=?",
            (position_id, producer),
        ).fetchone()[0]
        result = record_fact_run_in_transaction(
            db,
            position_id=position_id,
            producer=producer,
            detector_version=version,
            input_data={**inputs, "reactivation": latest},
            facts=facts,
        )
    return result
