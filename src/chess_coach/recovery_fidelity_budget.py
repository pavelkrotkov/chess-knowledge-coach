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


def _check_row(sizes, limit):
    # Covers both value/type tuples, object headers, pointers, and hidden rowid.
    total = 256 + 128 * len(sizes)
    for size in sizes:
        if not isinstance(size, int) or size < 0:
            raise ValueError("database row exceeds supported limit")
        total += size
        if total > limit:
            raise ValueError("database row exceeds supported limit")
    if total > limit:
        raise ValueError("database row exceeds supported limit")


def preflight(connection, table, deadline, limit):
    encoding = connection.execute("PRAGMA encoding").fetchone()[0]
    factor = 1 if encoding == b"UTF-8" else 2
    expressions = [_size_expression(field[0], factor) for field in columns(connection, table)]
    query = "SELECT " + ",".join(expressions) + " FROM " + identifier(table)
    for sizes in connection.execute(query):
        deadline.check()
        _check_row(sizes, limit)
