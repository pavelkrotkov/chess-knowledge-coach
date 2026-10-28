"""Private durable cursors for bounded Lichess synchronization."""

import sqlite3


def add_sync_progress(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS sync_progress (
            account_key TEXT PRIMARY KEY,
            revision INTEGER NOT NULL DEFAULT 0,
            next_kind TEXT NOT NULL DEFAULT 'recent' CHECK(next_kind IN ('recent', 'history')),
            history_start INTEGER NOT NULL,
            history_windows TEXT NOT NULL,
            history_cycles INTEGER NOT NULL DEFAULT 0,
            recent_windows TEXT NOT NULL,
            recent_end INTEGER NOT NULL,
            recent_target INTEGER NOT NULL
        )"""
    )


def add_sync_turn(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(sync_progress)")}
    if "next_kind" not in columns:
        connection.execute(
            "ALTER TABLE sync_progress ADD COLUMN next_kind TEXT NOT NULL DEFAULT 'recent' "
            "CHECK(next_kind IN ('recent', 'history'))"
        )
