"""Publish source-checked descriptive facts and review mappings atomically."""

from .fork_storage import fact_run
from .material_replay import source_inputs
from .material_source_marker import source_marker
from .rook_plan_lesson import VERSION
from .rook_plan_mapping import mapping

PRODUCER = "rook-plan-lesson"


def publish(db, prepared, fact):
    context = prepared["context"]
    inputs = source_inputs(prepared)
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if (
            source_marker(db, prepared["position_id"], prepared["game_id"], context["subject"])
            != prepared["source_marker"]
        ):
            raise ValueError("source changed")
        run = fact_run(
            db,
            prepared["position_id"],
            inputs,
            fact,
            producer=PRODUCER,
            version=VERSION,
            fact_type="rook_plan_lesson",
        )
        mapped = mapping(db, prepared, inputs, run, fact)
        db.connection.commit()
        return {**run, "mapping": mapped}
    except BaseException:
        db.connection.rollback()
        raise
