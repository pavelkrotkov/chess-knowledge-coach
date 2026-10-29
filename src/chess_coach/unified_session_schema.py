"""Durable direct-prompt session snapshots and idempotent events."""

import sqlite3


def add_unified_sessions(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS unified_sessions (
        attempt_id TEXT PRIMARY KEY, subject TEXT NOT NULL, source_type TEXT NOT NULL,
        source_version TEXT NOT NULL, source_key TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
        prompt_fen TEXT NOT NULL, learner_color TEXT NOT NULL, objective TEXT NOT NULL,
        lines_json TEXT NOT NULL, provenance_json TEXT NOT NULL, current_fen TEXT NOT NULL,
        candidates_json TEXT NOT NULL, next_index INTEGER NOT NULL, hints_used INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL CHECK(status IN (\u0027active\u0027,\u0027line_completed\u0027,
            \u0027objective_verified\u0027,\u0027needs_verification\u0027)),
        started_at TEXT NOT NULL, finished_at TEXT)""")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_unified_sessions_subject ON unified_sessions(subject,started_at DESC,attempt_id)"
    )
    connection.execute("""CREATE TABLE IF NOT EXISTS unified_session_events (
        attempt_id TEXT NOT NULL REFERENCES unified_sessions(attempt_id), event_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN (\u0027move\u0027,\u0027hint\u0027)), submitted_move TEXT,
        response_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(attempt_id,event_id))""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS unified_snapshot_immutable BEFORE UPDATE OF
        subject,source_type,source_version,source_key,snapshot_hash,prompt_fen,learner_color,
        objective,lines_json,provenance_json ON unified_sessions
        BEGIN SELECT RAISE(ABORT, \u0027unified session snapshot is immutable\u0027); END""")

    connection.execute("""CREATE TRIGGER IF NOT EXISTS unified_session_no_delete BEFORE DELETE ON unified_sessions
        BEGIN SELECT RAISE(ABORT, \u0027unified session history is immutable\u0027); END""")
    for action in ("UPDATE", "DELETE"):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS unified_event_no_{action.lower()}
            BEFORE {action} ON unified_session_events
            BEGIN SELECT RAISE(ABORT, \u0027unified event history is immutable\u0027); END""")
