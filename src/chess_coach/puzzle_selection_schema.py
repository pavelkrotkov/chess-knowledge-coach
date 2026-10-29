"""Add optional durable selection provenance to staged imports."""

import sqlite3


def add_puzzle_selection(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(puzzle_imports)")}
    if "selection_json" not in columns:
        connection.execute("ALTER TABLE puzzle_imports ADD COLUMN selection_json TEXT")
