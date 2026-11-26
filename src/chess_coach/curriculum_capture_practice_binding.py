"""Fingerprint bounded immutable practice records relevant to capture choice."""

from .capture_plan_history import LIMIT, _rows


def _counter(db, table, attempts):
    if not attempts:
        return (0, 0)
    placeholders = ",".join("?" for _ in attempts)
    row = db.connection.execute(
        f"SELECT count(*),coalesce(max(rowid),0) FROM {table} WHERE attempt_id IN ({placeholders})",
        attempts,
    ).fetchone()
    return tuple(row)


def practice(db, subject, check):
    rows = _rows(db, subject)
    limited = len(rows) > LIMIT
    attempts = [row["attempt_id"] for row in rows]
    values = [limited, *[tuple(row) for row in rows]]
    for table in ("unified_session_events", "objective_requests", "objective_results"):
        check()
        values.append(_counter(db, table, attempts))
    return values
