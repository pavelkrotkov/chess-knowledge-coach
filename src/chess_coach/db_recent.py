"""Apply recent schema upgrades in order."""

import sqlite3

from .classification_schema import add_classification_lineage
from .evidence_review_schema import add_evidence_reviews
from .evidence_schema import add_evidence_lineage
from .fact_schema import add_fact_lineage
from .lichess_schema import add_sync_turn
from .mastery_schema import allow_unknown_trend
from .puzzle_session_schema import add_puzzle_sessions
from .training_schema import add_training_scheduler_config


def upgrade_recent(connection: sqlite3.Connection, version: int) -> None:
    if version < 4:
        add_sync_turn(connection)
        connection.execute("PRAGMA user_version = 4")
    if version < 5:
        add_puzzle_sessions(connection)
        connection.execute("PRAGMA user_version = 5")
    if version < 6:
        add_fact_lineage(connection)
        connection.execute("PRAGMA user_version = 6")
    if version < 7:
        add_evidence_lineage(connection)
        connection.execute("PRAGMA user_version = 7")
    if version < 8:
        add_classification_lineage(connection)
        connection.execute("PRAGMA user_version = 8")
    _upgrade_learning(connection, version)


def _upgrade_learning(connection: sqlite3.Connection, version: int) -> None:
    if version < 9:
        add_evidence_reviews(connection)
        connection.execute("PRAGMA user_version = 9")
    if version < 10:
        add_training_scheduler_config(connection)
        connection.execute("PRAGMA user_version = 10")
    if version < 11:
        allow_unknown_trend(connection)
        connection.execute("PRAGMA user_version = 11")
