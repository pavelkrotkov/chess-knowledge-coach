"""Atomically publish material facts and unreviewed mappings after a source recheck."""

from .material_fact_storage import fact_run
from .material_mapping import mapping
from .material_source_marker import source_marker


def publish(db, prepared, fact):
    if db.connection.in_transaction:
        raise RuntimeError("material publication requires an idle database")
    context = prepared["context"]
    inputs = {
        "source_marker": prepared["source_marker"],
        "provenance": prepared["provenance"],
        "pre_move_fen": context["pre_move_fen"],
        "played_move": context["played_move"],
    }
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if (
            source_marker(db, prepared["position_id"], prepared["game_id"], context["subject"])
            != prepared["source_marker"]
        ):
            raise ValueError("material source changed")
        run = fact_run(db, prepared["position_id"], inputs, fact)
        result = mapping(db, prepared, inputs, run, fact)
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
