"""Apply ordered SQLite schema versions within one transaction."""

import sqlite3

from .analysis_schema import add_decision_columns
from .lichess_schema import add_sync_progress, add_sync_turn

CURRENT_VERSION = 4


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
        if version < 4:
            add_sync_turn(connection)
            connection.execute("PRAGMA user_version = 4")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
