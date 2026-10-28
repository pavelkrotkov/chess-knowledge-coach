"""Run each durable game stage and record sanitized outcomes."""

from .analysis import analyze_game
from .db import Database
from .pipeline_checkpoint import checkpoint
from .pipeline_config import PipelineConfig
from .pipeline_inputs import analysis_input, structure_input, tactical_input
from .pipeline_stage import run_stage
from .structure_episodes import extract_game_episodes
from .tactical_opportunities import record_game_opportunities


def run_analysis(
    db: Database, game_id: int, game_hash: str, config: PipelineConfig, engine_hash: str | None
):
    key = analysis_input(game_hash, config, engine_hash)

    def complete(connection, run_id):
        checkpoint(connection, game_id, "analysis", key, "complete", "ok", run_id)

    return run_stage(
        db,
        game_id,
        "analysis",
        key,
        lambda: analyze_game(
            db,
            game_id,
            config.engine_path,
            nodes=config.nodes,
            time_limit=config.seconds_per_position,
            threads=config.threads,
            hash_mb=config.hash_mb,
            on_complete=complete,
        ),
        atomic=True,
    )


def run_structures(db: Database, game_id: int, game_hash: str, config: PipelineConfig):
    key = structure_input(game_hash, config)

    def run(generation):
        extract_game_episodes(
            db, game_id, detector_version=config.structure_version, pipeline_generation=generation
        )
        row = db.connection.execute(
            'SELECT id FROM structure_runs WHERE game_id=? AND status="active" AND pipeline_generation=?',
            (game_id, generation),
        ).fetchone()
        if row is None:
            raise RuntimeError("structure output is not current")
        return row["id"]

    return run_stage(db, game_id, "structures", key, run, generated=True)


def run_tactical(
    db: Database, game_id: int, game_hash: str, config: PipelineConfig, analysis: dict
):
    key = tactical_input(db, game_id, game_hash, config, analysis["output_id"])
    if analysis["status"] != "complete":
        return {
            "stage": "tactical",
            "status": "blocked",
            "detail": "analysis_incomplete",
            "output_id": None,
            "replayed": False,
        }

    def run(generation):
        record_game_opportunities(
            db,
            game_id,
            learner=config.learner,
            ontology_version=config.ontology_version,
            pipeline_generation=generation,
            require_observation=True,
            detector_version=config.tactical_version,
        )
        return None

    return run_stage(db, game_id, "tactical", key, run, generated=True)
