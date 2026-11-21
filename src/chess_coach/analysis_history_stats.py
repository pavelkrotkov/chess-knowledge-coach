"""Analysis-specific table, index, and statistics allocation."""

import sqlite3

from .analysis_history_stats_layout import names as statistics_names


def allocation(connection):
    tables = (
        "analysis_runs",
        "analysis_provenance",
        "analysis_run_provenance",
        "analysis_provenance_settings",
    )
    available = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name IN (?,?,?,?)", tables
        )
    }
    if "analysis_runs" not in available:
        raise ValueError("analysis table allocation unavailable")
    names = {"sqlite_schema"} | available | set(statistics_names(connection))
    for table in available:
        names.update(
            row[0] for row in connection.execute("SELECT name FROM pragma_index_list(?)", (table,))
        )
    result = {}
    for name in names:
        try:
            row = connection.execute(
                """SELECT sum(pgsize),sum(payload),sum(unused),
                sum(CASE WHEN pagetype='leaf' THEN ncell ELSE 0 END)
                FROM dbstat WHERE name=?""",
                (name,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise ValueError("analysis table allocation unavailable") from exc
        if row[0] is None:
            raise ValueError("analysis table allocation unavailable")
        result[name] = tuple(row)
    return result, _native(connection, available, tables)


def _native(connection, available, tables):
    view = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='view' AND name='analysis_runs_read'"
    ).fetchone()
    return (
        available == set(tables)
        and view is not None
        and connection.execute("PRAGMA user_version").fetchone()[0] >= 33
    )
