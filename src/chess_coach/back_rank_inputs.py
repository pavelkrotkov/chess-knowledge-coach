"""Resolve and fingerprint the current game and prerequisite mate proof."""

import json

from .fact_fingerprint import canonical, digest
from .mate_auto_replay import replay
from .mate_inspection_source import source


def inputs(db, position, learner):
    snapshot, fingerprint = source(db, position, learner)
    prior = replay(db, position["id"], fingerprint, learner)
    run_id = prior["run_id"] if prior else None
    proof = None
    if run_id is not None:
        row = db.connection.execute(
            "SELECT payload_json FROM detector_facts WHERE run_id=? AND fact_type='bounded_mate'",
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError("mate proof unavailable")
        proof = json.loads(row["payload_json"]).get("proof")
    key = digest(canonical({"source": fingerprint, "mate_run": run_id, "version": "back-rank-v1"}))
    return snapshot, key, proof
