"""Replace the analysis table in the caller's transaction."""

import re


def _ddl(connection):
    row = connection.execute(
        "SELECT sql FROM sqlite_schema WHERE type='table' AND name='analysis_runs'"
    ).fetchone()
    if row is None or row[0] is None:
        raise ValueError("analysis table schema unavailable")
    sql, count = re.subn(
        r'^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?["`\[]?analysis_runs["`\]]?\s*',
        "CREATE TABLE analysis_runs_rebuild ",
        row[0],
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise ValueError("unsupported analysis table schema")
    objects = list(
        connection.execute(
            """SELECT sql FROM sqlite_schema
        WHERE tbl_name='analysis_runs' AND type IN ('index','trigger')
        AND sql IS NOT NULL ORDER BY type,name"""
        )
    )
    return sql, [row[0] for row in objects]


def swap(connection):
    sql, objects = _ddl(connection)
    connection.execute(sql)
    connection.execute("INSERT INTO analysis_runs_rebuild SELECT * FROM analysis_runs")
    connection.execute("DROP TABLE analysis_runs")
    connection.execute("ALTER TABLE analysis_runs_rebuild RENAME TO analysis_runs")
    for sql in objects:
        connection.execute(sql)
