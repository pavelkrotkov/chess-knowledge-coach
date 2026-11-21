"""Move inline run settings to the existing shared-provenance tables."""

from .analysis_history_links import link_value
from .analysis_provenance import attach, values

BATCH_SIZE = 8


def _pending(connection, last):
    where = "" if last is None else " AND r.id > ?"
    arguments = (BATCH_SIZE,) if last is None else (last, BATCH_SIZE)
    cursor = connection.execute(
        """SELECT r.id,r.config_json,r.nnue,r.compatibility_json FROM analysis_runs r
        WHERE NOT EXISTS (SELECT 1 FROM analysis_run_provenance p WHERE p.run_id=r.id)"""
        + where
        + " ORDER BY r.id LIMIT ?",
        arguments,
    )
    try:
        return cursor.fetchall()
    finally:
        cursor.close()


def compact(connection, deadline):
    original = connection.execute(
        "SELECT compact FROM analysis_provenance_settings WHERE id=1"
    ).fetchone()
    if original is None:
        raise ValueError("shared provenance setting unavailable")
    connection.execute("UPDATE analysis_provenance_settings SET compact=1 WHERE id=1")
    count = total = 0
    last = None
    while batch := _pending(connection, last):
        last = batch[-1][0]
        for run_id, config, nnue, compatibility in batch:
            deadline.check()
            config, nnue, compatibility, provenance = values(
                connection, config, nnue, compatibility
            )
            connection.execute(
                "UPDATE analysis_runs SET config_json=?,nnue=?,compatibility_json=? WHERE id=?",
                (config, nnue, compatibility, run_id),
            )
            if provenance is None:
                raise ValueError("shared provenance unavailable")
            attach(connection, run_id, provenance)
            count += 1
            total = (total + link_value(run_id, provenance)) % (1 << 256)
    if _pending(connection, None):
        raise ValueError("analysis conversion incomplete")
    connection.execute("UPDATE analysis_provenance_settings SET compact=? WHERE id=1", original)
    return count, total
