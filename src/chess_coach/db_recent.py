"""Apply recent schema upgrades in order."""

import sqlite3

from .analysis_comparison_schema import add_comparison_lines
from .classification_schema import add_classification_lineage
from .curriculum_schema import add_curriculum_index
from .deep_execution_schema import add_deep_execution
from .deep_selection_schema import add_deep_selection
from .evidence_review_schema import add_evidence_reviews
from .evidence_schema import add_evidence_lineage
from .fact_schema import add_fact_lineage
from .lichess_schema import add_sync_turn
from .mastery_schema import allow_unknown_trend
from .pipeline_cooldown_schema import add_pipeline_cooldown
from .pipeline_schema import add_pipeline_stages
from .public_training_schema import add_public_training
from .puzzle_import_schema import add_corpus_staging
from .puzzle_selection_schema import add_puzzle_selection
from .puzzle_session_schema import add_puzzle_sessions
from .training_completion_schema import add_training_completions
from .training_schema import add_training_scheduler_config
from .unified_session_schema import add_unified_sessions


def upgrade_recent(connection: sqlite3.Connection, version: int) -> None:
    upgrades = (
        (4, add_sync_turn),
        (5, add_puzzle_sessions),
        (6, add_fact_lineage),
        (7, add_evidence_lineage),
        (8, add_classification_lineage),
        (9, add_evidence_reviews),
        (10, add_training_scheduler_config),
        (11, allow_unknown_trend),
        (12, add_training_completions),
        (13, add_curriculum_index),
        (14, add_pipeline_stages),
        (15, add_pipeline_cooldown),
        (16, add_comparison_lines),
        (17, add_deep_selection),
        (18, add_corpus_staging),
        (19, add_deep_execution),
        (20, add_puzzle_selection),
        (21, add_public_training),
        (22, add_unified_sessions),
    )
    for target, apply_upgrade in upgrades:
        if version < target:
            apply_upgrade(connection)
            connection.execute(f"PRAGMA user_version = {target}")
