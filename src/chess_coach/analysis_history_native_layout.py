"""Recognize the native shared-provenance layout for capacity planning."""

import sqlite3
from contextlib import closing

from .analysis_history_columns import LINK_COLUMNS, PROFILE_COLUMNS, SETTING_COLUMNS, columns
from .analysis_provenance_schema import add_analysis_provenance


def _definitions(connection):
    names = (
        "analysis_provenance",
        "analysis_run_provenance",
        "analysis_provenance_settings",
        "analysis_runs_read",
        "analysis_provenance_no_update",
        "analysis_provenance_no_delete",
    )
    query = "SELECT name,sql FROM sqlite_schema WHERE name IN (?,?,?,?,?,?)"
    current = {row[0]: row[1] for row in connection.execute(query, names)}
    with closing(sqlite3.connect(":memory:")) as expected:
        expected.execute("CREATE TABLE analysis_runs(id INTEGER)")
        add_analysis_provenance(expected)
        reference = {row[0]: row[1] for row in expected.execute(query, names)}
    return len(current) == len(names) and current == reference


def native(connection):
    tables = (
        ("analysis_provenance", PROFILE_COLUMNS),
        ("analysis_run_provenance", LINK_COLUMNS),
        ("analysis_provenance_settings", SETTING_COLUMNS),
    )
    if not _tables(connection, tables):
        return False
    if any(
        connection.execute("SELECT 1 FROM pragma_index_list(?) LIMIT 1", (name,)).fetchone()
        for name in ("analysis_run_provenance", "analysis_provenance_settings")
    ):
        return False
    indexes = connection.execute("PRAGMA index_list(analysis_provenance)").fetchall()
    if len(indexes) != 1 or tuple(indexes[0][2:]) != (1, "u", 0):
        return False
    keys = connection.execute(
        "SELECT name,desc,coll FROM pragma_index_xinfo(?) WHERE key=1", (indexes[0][1],)
    ).fetchall()
    return [tuple(row) for row in keys] == [("fingerprint", 0, "BINARY")]


def _tables(connection, tables):
    return _definitions(connection) and all(
        columns(connection, name, expected) for name, expected in tables
    )
