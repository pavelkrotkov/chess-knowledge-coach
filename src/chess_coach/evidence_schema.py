"""Schema for immutable, producer-scoped evidence mapping runs."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS mapping_runs (
    id INTEGER PRIMARY KEY,
    producer TEXT NOT NULL, position_id INTEGER NOT NULL REFERENCES positions(id),
    subject TEXT NOT NULL, operation TEXT NOT NULL, scope_key TEXT NOT NULL,
    mapper_version TEXT NOT NULL, input_json TEXT NOT NULL, input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL, created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active', 'superseded')),
    supersedes_run_id INTEGER REFERENCES mapping_runs(id),
    UNIQUE(producer, position_id, subject, operation, scope_key, mapper_version, input_hash)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_mapping_scope
ON mapping_runs(producer, position_id, subject, operation, scope_key)
WHERE status = 'active';
CREATE TABLE IF NOT EXISTS evidence_fact_links (
    evidence_id INTEGER NOT NULL REFERENCES evidence_mappings(id),
    fact_id INTEGER NOT NULL REFERENCES detector_facts(id),
    subject TEXT NOT NULL, skill TEXT NOT NULL, operation TEXT NOT NULL,
    active INTEGER NOT NULL CHECK(active IN (0, 1)),
    PRIMARY KEY(evidence_id, fact_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_effective_fact_mapping
ON evidence_fact_links(fact_id, subject, skill, operation) WHERE active = 1;
"""


def add_evidence_lineage(connection: sqlite3.Connection) -> None:
    _column(
        connection, "evidence_mappings", "mapping_run_id", "INTEGER REFERENCES mapping_runs(id)"
    )
    _column(connection, "evidence_mappings", "source_provenance", "TEXT NOT NULL DEFAULT 'unknown'")
    _column(connection, "mastery_states", "is_stale", "INTEGER NOT NULL DEFAULT 0")
    for statement in SCHEMA.split(";"):
        if statement.strip():
            connection.execute(statement)


def _column(connection: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if name not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
