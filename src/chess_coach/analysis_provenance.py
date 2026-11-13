"""Store exact shared analysis settings only when the database opts in."""

from .analysis_provenance_schema import legacy
from .fact_fingerprint import canonical, digest


def values(connection, config, nnue, compatibility):
    if legacy(connection):
        return config, nnue, compatibility, None
    setting = connection.execute(
        "SELECT compact FROM analysis_provenance_settings WHERE id=1"
    ).fetchone()
    if setting is None:
        raise ValueError("analysis provenance setting unavailable")
    if not setting[0]:
        return config, nnue, compatibility, None
    fingerprint = digest(canonical([config, nnue, compatibility]))
    connection.execute(
        """INSERT OR IGNORE INTO analysis_provenance(fingerprint,config_json,nnue,compatibility_json)
        VALUES(?,?,?,?)""",
        (fingerprint, config, nnue, compatibility),
    )
    row = connection.execute(
        "SELECT id,config_json,nnue,compatibility_json FROM analysis_provenance WHERE fingerprint=?",
        (fingerprint,),
    ).fetchone()
    if row is None or tuple(row[1:]) != (config, nnue, compatibility):
        raise ValueError("analysis provenance identity conflict")
    return "", "", "", row[0]


def attach(connection, run_id, provenance_id):
    if provenance_id is not None:
        connection.execute(
            "INSERT INTO analysis_run_provenance(run_id,provenance_id) VALUES(?,?)",
            (run_id, provenance_id),
        )


def source_table(connection):
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='view' AND name='analysis_runs_read'"
    ).fetchone():
        return "analysis_runs_read"
    shared = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='analysis_run_provenance'"
    ).fetchone()
    if shared and connection.execute("SELECT 1 FROM analysis_run_provenance LIMIT 1").fetchone():
        raise ValueError("analysis provenance view unavailable")
    return "analysis_runs"
