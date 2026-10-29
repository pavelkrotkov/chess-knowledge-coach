"""Publish mate facts and mappings atomically after source recheck."""

from .fact_runs import record_fact_run_in_transaction
from .mapping_runs import record_mapping_run_in_transaction
from .mate_contract import MAPPER, MAPPER_VERSION, PRODUCER, VERSION
from .mate_inspection_source import still_current
from .mate_selection import mapping_skill as _skill


def publish(db, position, learner, fingerprint, fact, context):
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if not still_current(db, position, learner, fingerprint):
            raise ValueError("mate source changed")
        inputs = {"source_fingerprint": fingerprint}
        run = _fact_run(db, position["id"], inputs, fact)
        mapping = None
        if fact["status"] == "opportunity":
            mapping = _mapping(db, position, fingerprint, fact, run, context)
        db.connection.commit()
        return {
            "replayed": run["replayed"] and (mapping is None or mapping["replayed"]),
            "run_id": run["run_id"],
            "observation_status": fact["status"],
        }
    except BaseException:
        db.connection.rollback()
        raise


def _fact_run(db, position_id, inputs, fact):
    def record(data):
        return record_fact_run_in_transaction(
            db,
            position_id=position_id,
            producer=PRODUCER,
            detector_version=VERSION,
            input_data=data,
            facts=[{"fact_type": "bounded_mate", "payload": fact}],
        )

    run = record(inputs)
    if run["status"] != "active":
        latest = db.connection.execute(
            "SELECT MAX(id) FROM detector_runs WHERE producer=? AND position_id=?",
            (PRODUCER, position_id),
        ).fetchone()[0]
        run = record({**inputs, "reactivation": latest})
    return run


def _mapping(db, position, fingerprint, fact, run, context):
    details = {
        "source_fingerprint": fingerprint,
        "observation": fact,
        "pre_move_fen": context["pre_move_fen"],
        "qualification": "Bounded chess observation; no ability or cause inferred.",
    }
    return record_mapping_run_in_transaction(
        db,
        position_id=position["id"],
        producer=MAPPER,
        mapper_version=MAPPER_VERSION,
        subject=context["subject"],
        operation="execute",
        scope_key="bounded-mate-v1",
        input_data={"source_fingerprint": fingerprint, "fact_run": run["run_id"]},
        mappings=[
            {
                "skill": _skill(fact),
                "outcome": fact["outcome"],
                "confidence": 0.5,
                "fact_ids": run["fact_ids"],
                "context": details,
                "observation_at": context["observation_at"],
            }
        ],
    )
