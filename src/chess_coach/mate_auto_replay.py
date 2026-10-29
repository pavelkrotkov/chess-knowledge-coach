"""Validate and replay a matching current mate producer run."""

import json

from .fact_inputs import fact_batch
from .mate_contract import PRODUCER, VERSION
from .mate_mapping_current import mapping_current


def replay(db, position_id, fingerprint, subject):
    row = db.connection.execute(
        """SELECT d.id,d.input_json,d.output_hash,f.id AS fact_id,f.fact_key,f.payload_json
        FROM detector_runs d JOIN detector_facts f ON f.run_id=d.id
        WHERE d.position_id=? AND d.producer=? AND d.detector_version=? AND d.status=?
        AND f.fact_type='bounded_mate'""",
        (position_id, PRODUCER, VERSION, "active"),
    ).fetchone()
    if row is None:
        return None
    try:
        prior = json.loads(row["input_json"])["detector_input"]
        fact = json.loads(row["payload_json"])
        items, output_hash = fact_batch([{"fact_type": "bounded_mate", "payload": fact}])
    except (ValueError, TypeError, KeyError):
        raise ValueError("stored mate output is invalid") from None
    if prior.get("source_fingerprint") != fingerprint:
        return None
    if items[0][0] != row["fact_key"] or output_hash != row["output_hash"]:
        raise ValueError("stored mate output is invalid")
    if not mapping_current(db, fact, row["fact_id"], subject):
        return None
    return {"replayed": True, "run_id": row["id"], "observation_status": fact["status"]}
