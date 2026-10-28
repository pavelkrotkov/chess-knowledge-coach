"""Apply ordered SQLite schema versions within one transaction."""

import sqlite3

from .analysis_schema import add_decision_columns
from .lichess_schema import add_sync_progress, add_sync_turn
from .puzzle_session_schema import add_puzzle_sessions

CURRENT_VERSION = 5


def upgrade(connection: sqlite3.Connection, schema: str) -> None:
    from .db_migrations import upgrade_v1

    if connection.in_transaction:
        raise RuntimeError("cannot initialize during an existing transaction")
    try:
        connection.execute("BEGIN IMMEDIATE")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > CURRENT_VERSION:
            raise RuntimeError(f"unsupported schema version: {version}")
        if version < 1:
            upgrade_v1(connection, schema)
            connection.execute("PRAGMA user_version = 1")
        if version < 2:
            add_decision_columns(connection)
            connection.execute("PRAGMA user_version = 2")
        if version < 3:
            add_sync_progress(connection)
            connection.execute("PRAGMA user_version = 3")
        _upgrade_recent(connection, version)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _upgrade_recent(connection: sqlite3.Connection, version: int) -> None:
    if version < 4:
        add_sync_turn(connection)
        connection.execute("PRAGMA user_version = 4")
    if version < 5:
        add_puzzle_sessions(connection)
        connection.execute("PRAGMA user_version = 5")
