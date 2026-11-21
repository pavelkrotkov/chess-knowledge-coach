"""Validate the supported connection and analysis write triggers."""

from pathlib import Path


def _supported_triggers(connection):
    expected = {
        "analysis_provenance_no_update": "BEFORE UPDATE ON analysis_provenance",
        "analysis_provenance_no_delete": "BEFORE DELETE ON analysis_provenance",
    }
    rows = connection.execute(
        """SELECT name,sql FROM sqlite_schema WHERE type='trigger'
        AND tbl_name IN ('analysis_runs','analysis_provenance',
                         'analysis_run_provenance','analysis_provenance_settings')"""
    )
    for name, sql in rows:
        if name not in expected or expected[name] not in sql:
            raise ValueError("unsupported analysis write trigger")


def source(connection, root):
    if connection.in_transaction:
        raise ValueError("conversion requires a fresh connection")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise ValueError("foreign keys must be enabled before conversion")
    if connection.execute("PRAGMA synchronous").fetchone()[0] < 2:
        raise ValueError("conversion requires full SQLite synchronization")
    if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "delete":
        raise ValueError("conversion requires rollback journal mode")
    path = connection.execute("PRAGMA database_list").fetchone()[2]
    source = Path(path).resolve(strict=True)
    if not source.is_file() or not source.is_relative_to(root):
        raise ValueError("database must be a file inside the selected project")
    _supported_triggers(connection)
    if connection.execute("PRAGMA user_version").fetchone()[0] < 33:
        raise ValueError("native shared provenance schema is required")
    return source
