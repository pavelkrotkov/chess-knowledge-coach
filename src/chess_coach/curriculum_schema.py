"""Index bounded scans and track source changes between plan pages."""

import secrets
import sqlite3


def add_curriculum_index(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_puzzles_curriculum ON puzzles(corpus_id, rating, puzzle_id)"
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_curriculum_evidence
        ON evidence_mappings(subject, skill, operation, id)"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_curriculum_due ON training_items(julianday(due), id)
        WHERE source_type='puzzle' AND skill='mate_in_one' AND operation='execute' AND lower(due) != 'now'"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_curriculum_scheduled ON training_items(id)
        WHERE source_type='puzzle' AND skill='mate_in_one' AND operation='execute'"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS curriculum_source_revision
        (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL CHECK(revision >= 0),
         cursor_key BLOB NOT NULL)"""
    )
    connection.execute(
        "INSERT OR IGNORE INTO curriculum_source_revision(id,revision,cursor_key) VALUES(1,0,?)",
        (secrets.token_bytes(32),),
    )
    _source_triggers(connection)


def _source_triggers(connection: sqlite3.Connection) -> None:
    tables = (
        "training_items",
        "puzzle_corpora",
        "puzzles",
        "evidence_mappings",
        "evidence_review_events",
        "mapping_runs",
        "detector_runs",
        "evidence_fact_links",
        "games",
        "positions",
        "puzzle_sessions",
        "puzzle_session_events",
        "training_attempts",
        "training_completions",
    )
    for table in tables:
        for action in ("INSERT", "UPDATE", "DELETE"):
            name = f"curriculum_revision_{table}_{action.lower()}"
            connection.execute(
                f"""CREATE TRIGGER IF NOT EXISTS {name} AFTER {action} ON {table}
                BEGIN UPDATE curriculum_source_revision SET revision=revision+1 WHERE id=1; END"""
            )
