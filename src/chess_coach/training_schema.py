"""Record the actual scheduler settings without inventing legacy values."""

import sqlite3


def add_training_scheduler_config(connection: sqlite3.Connection) -> None:
    for table in ("training_items", "training_attempts"):
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if "scheduler_config_json" not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN scheduler_config_json TEXT")
