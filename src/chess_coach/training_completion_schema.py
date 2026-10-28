"""Durable links between verified puzzle attempts, evidence and schedule updates."""

import sqlite3


def add_training_completions(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS training_completions (
            attempt_id TEXT PRIMARY KEY REFERENCES puzzle_sessions(attempt_id),
            evidence_id INTEGER UNIQUE REFERENCES evidence_mappings(id),
            training_attempt_id INTEGER NOT NULL UNIQUE REFERENCES training_attempts(id),
            policy_version TEXT NOT NULL,
            mapper_version TEXT NOT NULL,
            evidence_reason TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS training_completion_no_update
        BEFORE UPDATE ON training_completions
        BEGIN SELECT RAISE(ABORT, 'training completions are immutable'); END"""
    )
    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS training_completion_no_delete
        BEFORE DELETE ON training_completions
        BEGIN SELECT RAISE(ABORT, 'training completions are immutable'); END"""
    )

    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS puzzle_session_snapshot_no_update
        BEFORE UPDATE OF corpus_version, corpus_checksum, puzzle_id, initial_fen, solution ON puzzle_sessions
        BEGIN SELECT RAISE(ABORT, 'puzzle snapshot is immutable'); END"""
    )

    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS completed_puzzle_no_update
        BEFORE UPDATE ON puzzle_sessions
        WHEN EXISTS (SELECT 1 FROM training_completions WHERE attempt_id = OLD.attempt_id)
        BEGIN SELECT RAISE(ABORT, 'completed puzzle attempts are immutable'); END"""
    )
    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS completed_puzzle_event_no_update
        BEFORE UPDATE ON puzzle_session_events
        WHEN EXISTS (SELECT 1 FROM training_completions WHERE attempt_id = OLD.attempt_id)
        BEGIN SELECT RAISE(ABORT, 'completed puzzle events are immutable'); END"""
    )
    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS completed_puzzle_event_no_delete
        BEFORE DELETE ON puzzle_session_events
        WHEN EXISTS (SELECT 1 FROM training_completions WHERE attempt_id = OLD.attempt_id)
        BEGIN SELECT RAISE(ABORT, 'completed puzzle events are immutable'); END"""
    )
    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS completed_training_attempt_no_update
        BEFORE UPDATE ON training_attempts
        WHEN EXISTS (SELECT 1 FROM training_completions WHERE training_attempt_id = OLD.id)
        BEGIN SELECT RAISE(ABORT, 'completed training attempts are immutable'); END"""
    )
