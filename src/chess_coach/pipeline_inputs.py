"""Fingerprint actual game, engine, and versioned opening inputs."""

import hashlib
from pathlib import Path

from .classification_inputs import opening_input
from .db import Database
from .fact_fingerprint import canonical, digest
from .pipeline_config import PipelineConfig
from .tactical_report import MAPPER_VERSION


def fingerprint(value) -> str:
    return digest(canonical(value))


def game_input(db: Database, game_id: int) -> str:
    row = db.connection.execute(
        "SELECT pgn,white,black,variant FROM games WHERE id=?", (game_id,)
    ).fetchone()
    positions = [
        list(item)
        for item in db.connection.execute(
            "SELECT id,ply,fen,uci FROM positions WHERE game_id=? ORDER BY ply", (game_id,)
        )
    ]
    return fingerprint({"game": list(row), "positions": positions})


def engine_identity(path: str) -> str | None:
    try:
        binary = Path(path).expanduser().resolve()
        if not binary.is_file():
            return None
        hasher = hashlib.sha256()
        with binary.open("rb") as file:
            for block in iter(lambda: file.read(1048576), b""):
                hasher.update(block)
        return hasher.hexdigest()
    except OSError:
        return None


def analysis_input(game_hash: str, config: PipelineConfig, engine_hash: str | None) -> str:
    return fingerprint(
        {
            "game": game_hash,
            "engine": engine_hash,
            "nodes": config.nodes,
            "seconds": config.seconds_per_position,
            "threads": config.threads,
            "hash_mb": config.hash_mb,
            "multipv": 1,
            "semantics": "same-board-roots-v1",
        }
    )


def structure_input(game_hash: str, config: PipelineConfig) -> str:
    return fingerprint({"game": game_hash, "detector": config.structure_version})


def tactical_input(
    db: Database, game_id: int, game_hash: str, config: PipelineConfig, analysis_id: int | None
) -> str:
    outputs = [
        list(row)
        for row in db.connection.execute(
            "SELECT e.id,e.position_id,e.best_move,e.decision_fen,e.score_pov,e.multipv FROM engine_outputs e JOIN positions p ON p.id=e.position_id WHERE p.game_id=? ORDER BY e.id",
            (game_id,),
        )
    ]
    return fingerprint(
        {
            "game": game_hash,
            "analysis_id": analysis_id,
            "engine_outputs": outputs,
            "learner": config.learner.strip().casefold(),
            "ontology": config.ontology_version,
            "detector": config.tactical_version,
            "mapper": MAPPER_VERSION,
        }
    )


def opening_stage_input(db: Database, game_id: int, config: PipelineConfig, game_hash: str):
    dataset = None
    if config.opening_version and config.opening_source:
        dataset = db.connection.execute(
            "SELECT id FROM opening_datasets WHERE version=? AND source_url=?",
            (config.opening_version, config.opening_source),
        ).fetchone()
    data = opening_input(db, game_id, dataset[0]) if dataset else None
    return fingerprint(
        {
            "game": game_hash,
            "dataset": data,
            "version": config.opening_version,
            "source": config.opening_source,
            "classifier": config.classifier_version,
        }
    ), dataset


def scan_input(db: Database, config: PipelineConfig, engine_hash: str | None) -> str:
    # Scheduling and network budgets do not change processing outputs.
    names = (
        "max_positions",
        "nodes",
        "seconds_per_position",
        "threads",
        "hash_mb",
        "opening_version",
        "opening_source",
        "structure_version",
        "classifier_version",
        "ontology_version",
        "tactical_version",
    )
    settings = {name: getattr(config, name) for name in names}
    dataset = db.connection.execute(
        "SELECT id,content_revision FROM opening_datasets WHERE version=? AND source_url=?",
        (config.opening_version, config.opening_source),
    ).fetchone()
    return fingerprint(
        {
            "settings": settings,
            "engine": engine_hash,
            "mapper": MAPPER_VERSION,
            "analysis_semantics": "same-board-roots-v1",
            "dataset": list(dataset) if dataset else None,
        }
    )
