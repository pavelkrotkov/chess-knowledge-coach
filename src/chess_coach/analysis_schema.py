"""Schema extension for unambiguous engine-decision provenance."""

import sqlite3


def add_decision_columns(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(engine_outputs)")}
    for column in ("decision_fen", "score_pov"):
        if column not in columns:
            connection.execute(f"ALTER TABLE engine_outputs ADD COLUMN {column} TEXT")
