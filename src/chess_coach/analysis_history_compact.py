"""Move inline run settings to the existing shared-provenance tables."""

from .analysis_history_links import link_value
from .analysis_provenance import attach, values


def compact(connection, deadline):
    original = connection.execute(
        "SELECT compact FROM analysis_provenance_settings WHERE id=1"
    ).fetchone()
    if original is None:
        raise ValueError("shared provenance setting unavailable")
    connection.execute("UPDATE analysis_provenance_settings SET compact=1 WHERE id=1")
    count = total = 0
    cursor = connection.execute(
        """SELECT r.id,r.config_json,r.nnue,r.compatibility_json FROM analysis_runs r
        WHERE NOT EXISTS (SELECT 1 FROM analysis_run_provenance p WHERE p.run_id=r.id)
        ORDER BY r.id"""
    )
    for run_id, config, nnue, compatibility in cursor:
        deadline.check()
        config, nnue, compatibility, provenance = values(connection, config, nnue, compatibility)
        connection.execute(
            "UPDATE analysis_runs SET config_json=?,nnue=?,compatibility_json=? WHERE id=?",
            (config, nnue, compatibility, run_id),
        )
        if provenance is None:
            raise ValueError("shared provenance unavailable")
        attach(connection, run_id, provenance)
        count += 1
        total = (total + link_value(run_id, provenance)) % (1 << 256)
    connection.execute("UPDATE analysis_provenance_settings SET compact=? WHERE id=1", original)
    return count, total
