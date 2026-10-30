"""Explicit resource budgets and versions for one processing invocation."""

from dataclasses import dataclass, field

from .pipeline_limits import validate_integer_limits, validate_other_limits
from .pipeline_versions import validate_learner
from .pipeline_worker_config import validate_worker_config


@dataclass(frozen=True)
class PipelineConfig:
    learner: str = field(repr=False)
    max_games: int = 25
    max_scan: int = 1000
    max_positions: int = 300
    nodes: int = 10000
    seconds_per_position: float = 1.0
    threads: int = 1
    hash_mb: int = 64
    engine_path: str = "/usr/games/stockfish"
    page_size: int = 100
    network_retries: int = 1
    network_requests: int = 50
    network_timeout: float = 30.0
    network_seconds: float = 120.0
    network_bytes: int = 8388608
    network_sleep: float = 60.0
    opening_version: str | None = None
    opening_source: str | None = None
    structure_version: str = "0.1.0"
    classifier_version: str = "1.1.0"
    ontology_version: str = "tactical-mate-v1"
    tactical_version: str = "1.0.0"
    deep_enabled: bool = True
    deep_max_scan: int = 100
    deep_max_games: int = 4
    deep_per_game: int = 4
    deep_max_jobs: int = 4
    deep_nodes: int = 50000
    deep_seconds: float = 2.0
    deep_multipv: int = 3
    mate_enabled: bool = True
    mate_max_scan: int = 200
    mate_max_decisions: int = 50
    material_enabled: bool = True
    material_max_scan: int = 200
    material_max_decisions: int = 50
    pawn_enabled: bool = True
    pawn_max_scan: int = 40
    pawn_max_decisions: int = 4

    def validate(self) -> None:
        validate_learner(self.learner)
        validate_integer_limits(self)
        validate_other_limits(self)
        validate_worker_config(self)
