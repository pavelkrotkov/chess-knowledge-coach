"""Recheck the source and atomically publish versioned pawn observations."""

from .pawn_coach_mapping import mapping
from .pawn_coach_storage import fact_run
from .pawn_inspection import _still_current
from .pawn_tables import open_verified


def _resources_current(prepared):
    tablebase = open_verified()
    available = tablebase is not None
    if tablebase is not None:
        tablebase.close()
    was_available = prepared["report"]["proof"].get("reason") != "proof_resources_unavailable"
    return available == was_available or prepared["fact"] is None


def publish(db, prepared, learner):
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if not _still_current(
            db, prepared["position"], learner, prepared["inputs"]["source_fingerprint"]
        ):
            raise ValueError("pawn source changed")
        if not _resources_current(prepared):
            raise ValueError("pawn resources changed")
        run = fact_run(db, prepared)
        mapped = mapping(db, prepared, run)
        db.connection.commit()
        return {
            "detector_run_id": run["run_id"],
            "fact_ids": run["fact_ids"],
            "mapping_run_id": mapped["run_id"] if mapped else None,
            "evidence_ids": mapped["evidence_ids"] if mapped else [],
            "replayed": run["replayed"],
            "skipped": False,
            "outcome": prepared["fact"]["outcome"] if prepared["fact"] else "unsupported",
        }
    except BaseException:
        db.connection.rollback()
        raise
