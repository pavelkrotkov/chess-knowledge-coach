"""Store processing checkpoints and explicit producer execution generations."""

import sqlite3


def add_pipeline_stages(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS pipeline_stages (
        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
        stage TEXT NOT NULL, input_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ("pending", "complete", "failed", "skipped")),
        detail TEXT NOT NULL, output_id INTEGER, output_hash TEXT, generation INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (game_id, stage)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS pipeline_cursors (
        account_key TEXT PRIMARY KEY, last_game_id INTEGER NOT NULL, updated_at TEXT NOT NULL,
        scan_hash TEXT
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS pipeline_health (
        id INTEGER PRIMARY KEY CHECK(id=1), status TEXT NOT NULL, started_at TEXT NOT NULL,
        finished_at TEXT, last_success_at TEXT, sync_status TEXT NOT NULL,
        sync_detail TEXT, sync_at TEXT, last_sync_success_at TEXT
    )""")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(opening_datasets)")}
    if "content_revision" not in columns:
        connection.execute(
            "ALTER TABLE opening_datasets ADD COLUMN content_revision INTEGER NOT NULL DEFAULT 0"
        )
    for table in ("opening_runs", "structure_runs"):
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if "pipeline_generation" not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN pipeline_generation INTEGER")
