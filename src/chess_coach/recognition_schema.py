"""Add private immutable first-encounter recognition history."""

import sqlite3


def add_recognition(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS recognition_attempts (
        attempt_id TEXT PRIMARY KEY, subject TEXT NOT NULL, prompt_key TEXT NOT NULL,
        prompt_fen TEXT NOT NULL, learner_color TEXT NOT NULL, source_version TEXT NOT NULL,
        source_key TEXT NOT NULL, source_url TEXT NOT NULL, source_game TEXT,
        source_fingerprint TEXT NOT NULL, proof_json TEXT NOT NULL,
        content_rating INTEGER NOT NULL, content_deviation INTEGER NOT NULL,
        content_opening TEXT, cue_status TEXT NOT NULL CHECK(cue_status='uncued'), started_at TEXT NOT NULL,
        UNIQUE(subject, prompt_key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS recognition_events (
        attempt_id TEXT PRIMARY KEY REFERENCES recognition_attempts(attempt_id),
        action TEXT NOT NULL CHECK(action IN ('answer', 'reveal')),
        answer TEXT CHECK(answer IN ('capture', 'mate', 'uncertain')),
        assisted INTEGER NOT NULL CHECK(assisted IN (0, 1)),
        created_at TEXT NOT NULL)""")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_recognition_subject ON recognition_attempts(subject, started_at DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_recognition_unified_prompt ON unified_sessions(prompt_fen)"
    )
    for table in ("recognition_attempts", "recognition_events"):
        for action in ("UPDATE", "DELETE"):
            connection.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'recognition history is immutable'); END"
            )
