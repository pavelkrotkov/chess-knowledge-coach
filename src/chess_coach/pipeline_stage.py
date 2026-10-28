"""Run a checkpointed stage and persist sanitized status."""

from .db import Database
from .mapping_transaction import mapping_transaction
from .pipeline_checkpoint import checkpoint, current, prepare_generation
from .pipeline_output import tactical_output_hash


def run_stage(
    db: Database, game_id: int, stage: str, key: str, action, *, atomic=False, generated=False
):
    old = current(db.connection, game_id, stage, key)
    if old is not None:
        return {
            "stage": stage,
            "status": old["status"],
            "detail": old["detail"],
            "output_id": old["output_id"],
            "replayed": True,
        }
    try:
        if generated:
            with mapping_transaction(db):
                generation = prepare_generation(db.connection, game_id, stage, key)
            output = action(generation)
        else:
            output = action()
        if atomic and current(db.connection, game_id, stage, key) is None:
            raise RuntimeError("atomic stage did not commit its checkpoint")
        if not atomic:
            with mapping_transaction(db):
                output_hash = (
                    tactical_output_hash(db.connection, game_id) if stage == "tactical" else None
                )
                checkpoint(
                    db.connection, game_id, stage, key, "complete", "ok", output, output_hash
                )
        return {
            "stage": stage,
            "status": "complete",
            "detail": "ok",
            "output_id": output,
            "replayed": False,
        }
    except Exception:
        with mapping_transaction(db):
            checkpoint(db.connection, game_id, stage, key, "failed", f"{stage}_failed")
        return {
            "stage": stage,
            "status": "failed",
            "detail": f"{stage}_failed",
            "output_id": None,
            "replayed": False,
        }
