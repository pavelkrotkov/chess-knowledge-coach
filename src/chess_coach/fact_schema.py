"""Schema for immutable, scoped detector runs and their facts."""

import sqlite3

RUN_TABLE = """
CREATE TABLE IF NOT EXISTS detector_runs (
    id INTEGER PRIMARY KEY,
    producer TEXT NOT NULL,
    position_id INTEGER NOT NULL REFERENCES positions(id),
    detector_version TEXT NOT NULL,
    input_json TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    produced_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active', 'superseded')),
    supersedes_run_id INTEGER REFERENCES detector_runs(id),
    UNIQUE(producer, position_id, detector_version, input_hash)
);
"""


def add_fact_lineage(connection: sqlite3.Connection) -> None:
    connection.execute(RUN_TABLE)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(detector_facts)")}
    definitions = {
        "run_id": "INTEGER REFERENCES detector_runs(id)",
        "fact_key": "TEXT",
        "produced_at": "TEXT",
    }
    for name, definition in definitions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE detector_facts ADD COLUMN {name} {definition}")
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_detector_run_active "
        "ON detector_runs(producer, position_id) WHERE status = 'active'"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_detector_fact_key ON detector_facts(run_id, fact_key)"
    )
