"""Append-only operator decisions on evidence."""

import sqlite3


def add_evidence_reviews(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence_mappings)")}
    if "legacy_validated" not in columns:
        connection.execute(
            "ALTER TABLE evidence_mappings ADD COLUMN legacy_validated INTEGER NOT NULL DEFAULT 0"
        )
        connection.execute("UPDATE evidence_mappings SET legacy_validated = human_validated")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS evidence_review_events (
            id INTEGER PRIMARY KEY,
            evidence_id INTEGER NOT NULL REFERENCES evidence_mappings(id),
            decision TEXT NOT NULL CHECK(decision IN ('accept', 'reject', 'revoke')),
            actor TEXT NOT NULL CHECK(length(trim(actor)) > 0),
            rationale TEXT,
            reviewed_at TEXT NOT NULL
        )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_review_history "
        "ON evidence_review_events(evidence_id, id)"
    )
    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS evidence_review_no_update
        BEFORE UPDATE ON evidence_review_events
        BEGIN SELECT RAISE(ABORT, 'review events are immutable'); END"""
    )
    connection.execute(
        """CREATE TRIGGER IF NOT EXISTS evidence_review_no_delete
        BEFORE DELETE ON evidence_review_events
        BEGIN SELECT RAISE(ABORT, 'review events are immutable'); END"""
    )
