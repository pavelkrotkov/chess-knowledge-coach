"""Reject history reuse when its read-only snapshot is absent."""


def require_read_snapshot(connection):
    if not connection.in_transaction:
        raise ValueError("preview snapshot is closed")
    if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise ValueError("preview snapshot is not read-only")
