"""Attest legacy row representations with bounded, short read queries."""

import time

from .schema_compat_layout import validate

CHUNK = 16000
CHECKS = (
    (
        "analysis_runs",
        "typeof(config_json)!='text' OR typeof(nnue)!='text' OR "
        "typeof(compatibility_json)!='text' OR "
        "(config_json='' AND nnue='' AND compatibility_json='')",
    ),
    (
        "detector_runs",
        "typeof(input_json)!='text' OR input_json='' OR "
        "typeof(input_hash)!='text' OR typeof(output_hash)!='text'",
    ),
    (
        "mapping_runs",
        "typeof(input_json)!='text' OR input_json='' OR "
        "typeof(input_hash)!='text' OR typeof(output_hash)!='text'",
    ),
)


def _inline(connection, table, condition):
    last = None
    while True:
        predicate = "" if last is None else "WHERE id>?"
        args = (CHUNK,) if last is None else (last, CHUNK)
        row = connection.execute(
            f"SELECT MAX(id),MAX(invalid) FROM (SELECT id,({condition}) AS invalid "
            f"FROM {table} {predicate} ORDER BY id LIMIT ?)",
            args,
        ).fetchone()
        if row[1]:
            raise ValueError("legacy representation unavailable")
        if row[0] is None:
            return
        last = row[0]


def inspect(connection, *, seconds=60.0):
    """Check schema and inline rows within a bounded, stable read."""
    deadline = time.monotonic() + seconds
    before = connection.execute("PRAGMA data_version").fetchone()[0]
    connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        validate(connection)
        for table, condition in CHECKS:
            _inline(connection, table, condition)
        if time.monotonic() >= deadline:
            raise ValueError("legacy preflight timed out")
        if connection.execute("PRAGMA data_version").fetchone()[0] != before:
            raise ValueError("database changed during legacy preflight")
        return connection.execute("PRAGMA schema_version").fetchone()[0]
    finally:
        connection.set_progress_handler(None, 0)
