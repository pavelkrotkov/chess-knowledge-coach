"""Ordered, atomic SQLite schema upgrades."""

from __future__ import annotations

import sqlite3

from .db_evidence import rebuild_evidence

CURRENT_VERSION = 1
COLUMNS = {
    "games": {"variant": "TEXT NOT NULL DEFAULT 'Standard'", "termination": "TEXT"},
    "evidence_mappings": {
        "human_validated": "INTEGER NOT NULL DEFAULT 0",
        "context_json": "TEXT NOT NULL DEFAULT '{}'",
        "subject": "TEXT NOT NULL DEFAULT 'default'",
    },
    "analysis_runs": {
        "binary_path": "TEXT NOT NULL DEFAULT ''",
        "binary_version": "TEXT NOT NULL DEFAULT ''",
        "nnue": "TEXT NOT NULL DEFAULT ''",
        "compatibility_json": "TEXT NOT NULL DEFAULT '{}'",
    },
    "engine_outputs": {"multipv": "INTEGER NOT NULL DEFAULT 1"},
    "maia_predictions": {"conditioning_elo": "INTEGER"},
}


def create_schema(connection: sqlite3.Connection, schema: str) -> None:
    statement = ""
    for line in schema.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        raise ValueError("incomplete schema statement")


def add_missing_columns(connection: sqlite3.Connection) -> None:
    for table, definitions in COLUMNS.items():
        existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for column, definition in definitions.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def upgrade_v1(connection: sqlite3.Connection, schema: str) -> None:
    create_schema(connection, schema)
    add_missing_columns(connection)
    rebuild_evidence(connection, schema)


def upgrade(connection: sqlite3.Connection, schema: str) -> None:
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
        connection.commit()
    except Exception:
        connection.rollback()
        raise
