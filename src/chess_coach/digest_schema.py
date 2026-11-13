"""Add default-off compact digests and preserve hexadecimal read views."""

import sqlite3


def _hex(column):
    return f"CASE WHEN typeof({column})='blob' THEN lower(hex({column})) ELSE {column} END"


def add_digest_storage(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS digest_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), compact INTEGER NOT NULL CHECK(compact IN (0,1)))""")
    connection.execute("INSERT OR IGNORE INTO digest_settings(id,compact) VALUES(1,0)")
    connection.execute("DROP VIEW IF EXISTS detector_runs_read")
    input_hash = _hex("d.input_hash")
    connection.execute(f"""CREATE VIEW detector_runs_read AS
        SELECT d.id,d.producer,d.position_id,d.detector_version,
        CASE WHEN d.input_json='' THEN COALESCE(shared.input_json, '!missing-detector-input!') ELSE d.input_json END AS input_json,
        {input_hash} AS input_hash,{_hex("d.output_hash")} AS output_hash,
        d.produced_at,d.status,d.supersedes_run_id
        FROM detector_runs d LEFT JOIN detector_inputs shared
        ON d.input_json='' AND shared.input_hash={input_hash}""")
    connection.execute(f"""CREATE VIEW IF NOT EXISTS mapping_runs_read AS
        SELECT m.id,m.producer,m.position_id,m.subject,m.operation,m.scope_key,m.mapper_version,
        m.input_json,{_hex("m.input_hash")} AS input_hash,{_hex("m.output_hash")} AS output_hash,
        m.created_at,m.status,m.supersedes_run_id FROM mapping_runs m""")
