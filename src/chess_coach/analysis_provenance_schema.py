"""Add optional shared analysis provenance without rewriting existing runs."""

import sqlite3


def add_analysis_provenance(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_provenance (
        id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE,
        config_json TEXT NOT NULL, nnue TEXT NOT NULL, compatibility_json TEXT NOT NULL)""")
    for operation in ("UPDATE", "DELETE"):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS analysis_provenance_no_{operation.lower()}
            BEFORE {operation} ON analysis_provenance
            BEGIN SELECT RAISE(ABORT, 'analysis provenance is immutable'); END""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_provenance_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), compact INTEGER NOT NULL CHECK(compact IN (0,1)))""")
    connection.execute("INSERT OR IGNORE INTO analysis_provenance_settings(id,compact) VALUES(1,0)")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_run_provenance (
        run_id INTEGER PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE,
        provenance_id INTEGER NOT NULL REFERENCES analysis_provenance(id))""")
    connection.execute("""CREATE VIEW IF NOT EXISTS analysis_runs_read AS
        SELECT r.id,r.game_id,r.engine,r.engine_version,
        CASE WHEN link.run_id IS NULL THEN r.config_json ELSE p.config_json END AS config_json,
        r.binary_path,r.binary_version,
        CASE WHEN link.run_id IS NULL THEN r.nnue ELSE p.nnue END AS nnue,
        CASE WHEN link.run_id IS NULL THEN r.compatibility_json ELSE p.compatibility_json END AS compatibility_json,
        r.created_at FROM analysis_runs r
        LEFT JOIN analysis_run_provenance link ON link.run_id=r.id
        LEFT JOIN analysis_provenance p ON p.id=link.provenance_id""")


def legacy(connection):
    if connection.execute("PRAGMA user_version").fetchone()[0] >= 33:
        return False
    objects = dict(
        connection.execute(
            "SELECT name,type FROM sqlite_master WHERE name IN (?,?,?,?)",
            (
                "analysis_provenance",
                "analysis_provenance_settings",
                "analysis_run_provenance",
                "analysis_runs_read",
            ),
        ).fetchall()
    )
    if not objects:
        return True
    if objects != {
        "analysis_provenance": "table",
        "analysis_provenance_settings": "table",
        "analysis_run_provenance": "table",
        "analysis_runs_read": "view",
    }:
        raise ValueError("analysis provenance schema unavailable")
    setting = connection.execute(
        "SELECT compact FROM analysis_provenance_settings WHERE id=1"
    ).fetchone()
    links = connection.execute("SELECT 1 FROM analysis_run_provenance LIMIT 1").fetchone()
    if setting is None or setting[0] or links:
        raise ValueError("analysis provenance schema unavailable")
    return True
