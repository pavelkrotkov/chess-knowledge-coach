"""Ordered, immutable facts for coach-provided tactical positions."""

from datetime import UTC, datetime


def add_tactical_exposure(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS tactical_exposure_coverage (
        id INTEGER PRIMARY KEY CHECK(id=1), tracking_started_at TEXT NOT NULL)""")
    connection.execute(
        "INSERT OR IGNORE INTO tactical_exposure_coverage VALUES(1,?)",
        (datetime.now(UTC).isoformat(),),
    )
    connection.execute("""CREATE TABLE IF NOT EXISTS tactical_exposures (
        id INTEGER PRIMARY KEY, subject TEXT NOT NULL, prompt_key TEXT NOT NULL,
        artifact_hash TEXT NOT NULL, chapter_index INTEGER NOT NULL, chapter_hash TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('served','download','study_pending','study_verified','historical_unknown')),
        occurred_at TEXT NOT NULL,
        UNIQUE(subject,prompt_key,artifact_hash,chapter_index,kind))""")
    connection.execute("""CREATE INDEX IF NOT EXISTS idx_tactical_exposure_prompt
        ON tactical_exposures(subject,prompt_key,kind,occurred_at)""")
    for action in ("UPDATE", "DELETE"):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS tactical_exposures_no_{action.lower()}
            BEFORE {action} ON tactical_exposures
            BEGIN SELECT RAISE(ABORT, 'tactical exposure history is immutable'); END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS curriculum_revision_tactical_exposures_insert
        AFTER INSERT ON tactical_exposures
        BEGIN UPDATE curriculum_source_revision SET revision=revision+1 WHERE id=1; END""")
