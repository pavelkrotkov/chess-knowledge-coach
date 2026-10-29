"""Publish back-rank facts and mappings atomically after source recheck."""

from .back_rank_contract import FACT_TYPE, MAPPER, PRODUCER, VERSION
from .back_rank_inputs import inputs
from .back_rank_outcomes import outcomes, status
from .fact_runs import record_fact_run_in_transaction
from .mapping_runs import record_mapping_run_in_transaction


def publish(db, position, key, fact, context):
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if inputs(db, position, context["subject"])[1] != key:
            raise ValueError("back-rank source changed")
        run = _fact_run(db, position["id"], key, fact)
        for operation, outcome in outcomes(fact):
            _mapping(db, position, key, fact, run, context, operation, outcome)
        db.connection.commit()
        return {
            "replayed": run["replayed"],
            "run_id": run["run_id"],
            "observation_status": status(fact),
        }
    except BaseException:
        db.connection.rollback()
        raise


def _fact_run(db, position_id, key, fact):
    def record(data):
        return record_fact_run_in_transaction(
            db,
            position_id=position_id,
            producer=PRODUCER,
            detector_version=VERSION,
            input_data=data,
            facts=[{"fact_type": FACT_TYPE, "payload": fact}],
        )

    run = record({"source_fingerprint": key})
    if run["status"] != "active":
        latest = db.connection.execute(
            "SELECT MAX(id) FROM detector_runs WHERE producer=? AND position_id=?",
            (PRODUCER, position_id),
        ).fetchone()[0]
        run = record({"source_fingerprint": key, "reactivation": latest})
    return run


def _mapping(db, position, key, fact, run, context, operation, outcome):
    details = {
        "source_fingerprint": key,
        "observation": fact,
        "pre_move_fen": context["pre_move_fen"],
        "qualification": "Bounded next-move or short-mate proof; no overall safety, intent or ability inferred.",
    }
    return record_mapping_run_in_transaction(
        db,
        position_id=position["id"],
        producer=MAPPER,
        mapper_version=VERSION,
        subject=context["subject"],
        operation=operation,
        scope_key="back-rank-" + operation,
        input_data={"source_fingerprint": key, "fact_run": run["run_id"]},
        mappings=[
            {
                "skill": "back_rank",
                "outcome": outcome,
                "confidence": 0.5,
                "fact_ids": run["fact_ids"],
                "context": details,
                "observation_at": context["observation_at"],
            }
        ],
    )
