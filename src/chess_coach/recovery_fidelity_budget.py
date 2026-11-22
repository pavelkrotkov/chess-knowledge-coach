"""Bound aggregate row payload before opening any payload cursor."""

from .recovery_fidelity_schema import identifier
from .recovery_fidelity_tables import columns


def _size_expression(name, text_factor):
    value = identifier(name)
    return (
        "CASE typeof("
        + value
        + ") WHEN 'text' THEN length(CAST("
        + value
        + " AS BLOB))*"
        + str(text_factor)
        + " WHEN 'blob' THEN length("
        + value
        + ") "
        + "WHEN 'null' THEN 0 ELSE 8 END"
    )


def preflight(connection, table, deadline, limit):
    deadline.check()
    encoding = connection.execute("PRAGMA encoding").fetchone()[0]
    factor = 1 if encoding == b"UTF-8" else 2
    fields = columns(connection, table)
    expressions = [_size_expression(field[0], factor) for field in fields]
    overhead = 256 + 128 * len(fields)
    total = "+".join([str(overhead), *expressions])
    query = "SELECT 1 FROM " + identifier(table) + " WHERE (" + total + ") > ? LIMIT 1"
    deadline.check()
    oversized = connection.execute(query, (limit,)).fetchone()
    deadline.check()
    if oversized is not None:
        raise ValueError("database row exceeds supported limit")
