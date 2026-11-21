"""Check schema, dependent rows and resolved runs before committing."""

from .analysis_history_links import links
from .analysis_history_verify import dependents, resolved


def _schema(connection):
    return list(
        connection.execute(
            """SELECT type,name,tbl_name,sql FROM sqlite_schema
        WHERE NOT (type='table' AND name='analysis_runs') ORDER BY type,name"""
        )
    )


def foreign_keys(connection):
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("analysis foreign key check failed")


def after_swap(connection, deadline, before_schema, before_dependents):
    if (
        _schema(connection) != before_schema
        or dependents(connection, deadline) != before_dependents
    ):
        raise ValueError("analysis dependent or schema changed")
    foreign_keys(connection)


def after_compaction(
    connection, deadline, before_runs, before_dependents, before_links, count, added_links
):
    after_dependents = dependents(connection, deadline)
    before_dependents.pop(b"analysis_run_provenance")
    after_dependents.pop(b"analysis_run_provenance")
    if before_dependents != after_dependents:
        raise ValueError("analysis dependent changed")
    expected_links = (before_links[0] + count, (before_links[1] + added_links) % (1 << 256))
    if links(connection, deadline) != expected_links:
        raise ValueError("analysis provenance links changed")
    if resolved(connection, deadline) != before_runs:
        raise ValueError("analysis logical rows changed")
    foreign_keys(connection)
