"""Validate the legacy schema against the existing migration definitions."""

import sqlite3

from .analysis_schema import add_decision_columns
from .db import SCHEMA
from .db_migrations import upgrade_v1
from .db_recent import upgrade_recent
from .lichess_schema import add_sync_progress

FORBIDDEN = (
    "analysis_provenance",
    "analysis_provenance_settings",
    "analysis_run_provenance",
    "analysis_runs_read",
    "detector_inputs",
    "detector_input_settings",
    "detector_runs_read",
    "digest_settings",
    "mapping_runs_read",
)
VIEWS = ("analysis_runs_read", "detector_runs_read", "mapping_runs_read")
TABLES = (
    "analysis_run_provenance",
    "analysis_provenance_settings",
    "analysis_provenance",
    "detector_input_settings",
    "detector_inputs",
    "digest_settings",
)


def _expected():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("BEGIN")
        upgrade_v1(connection, SCHEMA)
        add_decision_columns(connection)
        add_sync_progress(connection)
        upgrade_recent(connection, 3, through=32)
        objects = connection.execute(
            "SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        tables = [name for name, kind in objects if kind == "table"]
        columns = {name: _columns(connection, name) for name in tables}
        return set(objects), columns
    finally:
        connection.close()


def _columns(connection, name):
    return {
        (row[1], row[2].upper(), row[3], row[5])
        for row in connection.execute("SELECT * FROM pragma_table_info(?)", (name,))
    }


def validate(connection):
    if connection.execute("PRAGMA user_version").fetchone()[0] != 32:
        raise ValueError("schema compatibility requires version 32")
    objects = {
        tuple(row)
        for row in connection.execute(
            "SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
    }
    if any(name in FORBIDDEN for name, _ in objects):
        raise ValueError("newer schema objects are present")
    expected, columns = _expected()
    if not expected.issubset(objects):
        raise ValueError("legacy schema is incomplete")
    if any(_columns(connection, table) != expected for table, expected in columns.items()):
        raise ValueError("legacy table columns differ")
