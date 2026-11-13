"""Add opt-in shared detector inputs without rewriting historical runs."""

import sqlite3


def add_detector_inputs(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS detector_inputs (
        input_hash TEXT PRIMARY KEY, input_json TEXT NOT NULL) WITHOUT ROWID""")
    for operation in ("UPDATE", "DELETE"):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS detector_inputs_no_{operation.lower()}
            BEFORE {operation} ON detector_inputs
            BEGIN SELECT RAISE(ABORT, 'detector inputs are immutable'); END""")
    connection.execute("""CREATE TABLE IF NOT EXISTS detector_input_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), compact INTEGER NOT NULL CHECK(compact IN (0,1)))""")
    connection.execute("INSERT OR IGNORE INTO detector_input_settings(id,compact) VALUES(1,0)")
    connection.execute("""CREATE VIEW IF NOT EXISTS detector_runs_read AS
        SELECT d.id,d.producer,d.position_id,d.detector_version,
        CASE WHEN d.input_json = '' THEN COALESCE(shared.input_json, '!missing-detector-input!') ELSE d.input_json END AS input_json,
        d.input_hash,d.output_hash,d.produced_at,d.status,d.supersedes_run_id
        FROM detector_runs d LEFT JOIN detector_inputs shared ON d.input_json = '' AND shared.input_hash=d.input_hash""")


def legacy(connection: sqlite3.Connection) -> bool:
    if connection.execute("PRAGMA user_version").fetchone()[0] >= 34:
        return False
    objects = dict(
        connection.execute(
            "SELECT name,type FROM sqlite_master WHERE name IN (?,?,?)",
            ("detector_inputs", "detector_input_settings", "detector_runs_read"),
        ).fetchall()
    )
    if not objects:
        if connection.execute("SELECT 1 FROM detector_runs WHERE input_json='' LIMIT 1").fetchone():
            raise ValueError("detector input schema unavailable")
        return True
    if objects != {
        "detector_inputs": "table",
        "detector_input_settings": "table",
        "detector_runs_read": "view",
    }:
        raise ValueError("detector input schema unavailable")
    setting = connection.execute(
        "SELECT compact FROM detector_input_settings WHERE id=1"
    ).fetchone()
    if (
        setting is None
        or setting[0]
        or connection.execute("SELECT 1 FROM detector_inputs LIMIT 1").fetchone()
    ):
        raise ValueError("detector input schema unavailable")
    return True
