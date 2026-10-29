"""Bounded settings and reproducible configuration for a deep search."""

from dataclasses import dataclass

from .analysis import detect_compatibility
from .analysis_configuration import engine_config
from .analysis_validation import prepare
from .deep_execution_limits import validate_options


@dataclass(frozen=True)
class DeepOptions:
    engine_path: str = "/usr/games/stockfish"
    nodes: int = 50000
    seconds: float = 2.0
    multipv: int = 3
    threads: int = 1
    hash_mb: int = 64
    min_depth: int = 4
    max_jobs: int = 4
    retry_insufficient: bool = False


def prepare_config(db, game_id, options):
    validate_options(options)
    try:
        binary, game = prepare(
            db.connection,
            game_id,
            options.engine_path,
            options.nodes,
            None,
            options.multipv,
            options.threads,
            options.hash_mb,
        )
    except RuntimeError:
        raise RuntimeError("deep engine is unavailable") from None
    config = engine_config(
        binary,
        options.nodes,
        options.seconds,
        None,
        options.multipv,
        options.threads,
        options.hash_mb,
        detect_compatibility(),
    )
    config.update(
        {
            "deep_semantics": "selected-decision-v1",
            "min_depth": options.min_depth,
            "stability_policy": "deep-stability-v1",
        }
    )
    return binary, game, config
