"""Run optional opening classification with explicit missing-data status."""

from typing import cast

from .db import Database
from .mapping_transaction import mapping_transaction
from .opening_classification import classify_game
from .pipeline_checkpoint import checkpoint, current
from .pipeline_config import PipelineConfig
from .pipeline_inputs import opening_stage_input
from .pipeline_stage import run_stage


def run_opening(db: Database, game_id: int, game_hash: str, config: PipelineConfig):
    key, dataset = opening_stage_input(db, game_id, config, game_hash)
    if dataset is None:
        previous = current(db.connection, game_id, "opening", key)
        if previous is not None:
            return {
                "stage": "opening",
                "status": "skipped",
                "detail": previous["detail"],
                "output_id": None,
                "replayed": True,
            }
        detail = (
            "opening_not_configured"
            if config.opening_version is None
            else "opening_dataset_missing"
        )
        with mapping_transaction(db):
            checkpoint(db.connection, game_id, "opening", key, "skipped", detail)
        return {
            "stage": "opening",
            "status": "skipped",
            "detail": detail,
            "output_id": None,
            "replayed": False,
        }

    def run(generation):
        classify_game(
            db,
            game_id,
            version=cast(str, config.opening_version),
            source_url=cast(str, config.opening_source),
            classifier_version=config.classifier_version,
            pipeline_generation=generation,
        )
        row = db.connection.execute(
            'SELECT id FROM opening_runs WHERE game_id=? AND status="active" AND pipeline_generation=?',
            (game_id, generation),
        ).fetchone()
        if row is None:
            raise RuntimeError("opening output is not current")
        return row["id"]

    return run_stage(db, game_id, "opening", key, run, generated=True)
