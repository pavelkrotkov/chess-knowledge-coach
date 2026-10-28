"""Durable puzzle attempts and idempotent learner events."""

import sqlite3


def add_puzzle_sessions(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS puzzle_sessions (
            attempt_id TEXT PRIMARY KEY,
            corpus_version TEXT NOT NULL,
            corpus_checksum TEXT NOT NULL,
            puzzle_id TEXT NOT NULL,
            initial_fen TEXT NOT NULL,
            solution TEXT NOT NULL,
            current_fen TEXT NOT NULL,
            next_index INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('active', 'solved', 'failed')),
            hints_used INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            finished_at TEXT
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS puzzle_session_events (
            attempt_id TEXT NOT NULL REFERENCES puzzle_sessions(attempt_id) ON DELETE CASCADE,
            event_id TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('move', 'hint')),
            submitted_move TEXT,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(attempt_id, event_id)
        )"""
    )
