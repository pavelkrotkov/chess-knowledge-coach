"""Validate exact back-rank detector and mapping lineage."""

import json

from .back_rank_contract import FACT_TYPE, PRODUCER, VERSION
from .material_opportunity_links import valid_link


def valid(db, evidence, fact):
    return (
        evidence["lifecycle_status"] == "active"
        and evidence["mapper_version"] == VERSION
        and fact["detector_status"] == "active"
        and fact["producer"] == PRODUCER
        and fact["fact_type"] == FACT_TYPE
        and fact["detector_version"] == fact["run_detector_version"] == VERSION
        and isinstance(fact["payload"], dict)
        and valid_link(db, evidence, fact)
    )


def recorded_key(db, fact):
    row = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (fact["detector_run_id"],)
    ).fetchone()
    try:
        return json.loads(row["input_json"])["detector_input"]["source_fingerprint"]
    except (TypeError, ValueError, KeyError):
        raise ValueError("back-rank opportunity unavailable") from None
