"""Publish a fork fact and mapping after rechecking its consumed source."""

from .fork_mapping import mapping
from .fork_storage import fact_run
from .material_replay import source_inputs
from .material_source_marker import source_marker


def publish(db, prepared, fact, *, fact_writer=fact_run, mapping_writer=mapping):
    if db.connection.in_transaction:
        raise RuntimeError("fork publication requires an idle database")
    inputs = source_inputs(prepared)
    context = prepared["context"]
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if (
            source_marker(db, prepared["position_id"], prepared["game_id"], context["subject"])
            != prepared["source_marker"]
        ):
            raise ValueError("fork source changed")
        run = fact_writer(db, prepared["position_id"], inputs, fact)
        result = mapping_writer(db, prepared, inputs, run, fact)
        db.connection.commit()
        return {
            "detector_run_id": run["run_id"],
            "fact_ids": run["fact_ids"],
            "mapping_run_id": result["run_id"] if result else None,
            "evidence_ids": result["evidence_ids"] if result else [],
            "replayed": run["replayed"],
            "outcome": fact["outcome"] if fact else "no_opportunity",
        }
    except BaseException:
        db.connection.rollback()
        raise
