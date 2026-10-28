"""Migrate classification output to append-only, versioned generations."""

import sqlite3

RUNS = """
CREATE TABLE IF NOT EXISTS structure_runs (
 id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id),
 detector_version TEXT NOT NULL, input_hash TEXT NOT NULL, output_hash TEXT NOT NULL,
 produced_at TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','superseded')),
 supersedes_run_id INTEGER REFERENCES structure_runs(id),
 UNIQUE(game_id, detector_version, input_hash)
);
CREATE UNIQUE INDEX IF NOT EXISTS structure_active_run ON structure_runs(game_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS opening_runs (
 id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id),
 dataset_id INTEGER NOT NULL REFERENCES opening_datasets(id), classifier_version TEXT NOT NULL,
 input_hash TEXT NOT NULL, output_hash TEXT NOT NULL, produced_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','superseded')),
 supersedes_run_id INTEGER REFERENCES opening_runs(id),
 UNIQUE(game_id, dataset_id, classifier_version, input_hash)
);
CREATE UNIQUE INDEX IF NOT EXISTS opening_active_run ON opening_runs(game_id) WHERE status='active';
"""
STRUCTURE = """
CREATE TABLE structure_episodes_new (
 id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
 start_ply INTEGER NOT NULL, end_ply INTEGER NOT NULL, features_json TEXT NOT NULL,
 structure_json TEXT NOT NULL, confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
 detector_version TEXT NOT NULL, run_id INTEGER REFERENCES structure_runs(id),
 produced_at TEXT, UNIQUE(run_id, start_ply, end_ply)
)
"""
OPENING = """
CREATE TABLE game_openings_new (
 id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
 dataset_id INTEGER NOT NULL REFERENCES opening_datasets(id) ON DELETE CASCADE,
 opening_node_id INTEGER REFERENCES opening_nodes(id),
 confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
 run_id INTEGER REFERENCES opening_runs(id), produced_at TEXT,
 UNIQUE(run_id)
)
"""


def add_classification_lineage(connection: sqlite3.Connection) -> None:
    for statement in RUNS.split(";"):
        if statement.strip():
            connection.execute(statement)
    _rebuild(connection, "structure_episodes", STRUCTURE)
    _rebuild(connection, "game_openings", OPENING)
    connection.execute("""CREATE VIEW IF NOT EXISTS current_structure_episodes AS
        SELECT e.* FROM structure_episodes e JOIN structure_runs r ON r.id=e.run_id
        WHERE r.status='active'""")
    connection.execute("""CREATE VIEW IF NOT EXISTS current_game_openings AS
        SELECT o.* FROM game_openings o JOIN opening_runs r ON r.id=o.run_id
        WHERE r.status='active'""")


def _rebuild(connection: sqlite3.Connection, table: str, ddl: str) -> None:
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    if "run_id" in columns and "produced_at" in columns:
        return
    _reject_external_references(connection, table)
    objects = connection.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type IN ('index','trigger') "
        "AND sql IS NOT NULL ORDER BY type,name",
        (table,),
    ).fetchall()
    connection.execute(ddl)
    destination = {row[1] for row in connection.execute(f"PRAGMA table_info({table}_new)")}
    if not set(columns) <= destination:
        raise RuntimeError(f"cannot upgrade {table} with unknown columns")
    names = ", ".join('"' + name.replace('"', '""') + '"' for name in columns)
    connection.execute(f"INSERT INTO {table}_new ({names}) SELECT {names} FROM {table}")
    connection.execute(f"DROP TABLE {table}")
    connection.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    for (sql,) in objects:
        connection.execute(sql)


def _reject_external_references(connection: sqlite3.Connection, table: str) -> None:
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        quoted = name.replace('"', '""')
        if any(
            row[2] == table for row in connection.execute(f'PRAGMA foreign_key_list("{quoted}")')
        ):
            raise RuntimeError(f"cannot upgrade {table} with external foreign keys")
