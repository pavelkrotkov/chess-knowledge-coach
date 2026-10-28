"""Apply recent schema upgrades in order."""

import sqlite3

from .classification_schema import add_classification_lineage
from .evidence_review_schema import add_evidence_reviews
from .evidence_schema import add_evidence_lineage
from .fact_schema import add_fact_lineage
from .lichess_schema import add_sync_turn
from .puzzle_session_schema import add_puzzle_sessions


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
    if version < 9:
        add_evidence_reviews(connection)
        connection.execute("PRAGMA user_version = 9")
