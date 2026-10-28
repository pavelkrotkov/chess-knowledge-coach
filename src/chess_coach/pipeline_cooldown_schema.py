"""Add a durable server-directed retry deadline to pipeline health."""

import sqlite3


def add_pipeline_cooldown(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(pipeline_health)")}
    if "retry_until" not in columns:
        connection.execute("ALTER TABLE pipeline_health ADD COLUMN retry_until TEXT")
