"""Report the selected corpus without materializing its puzzles."""

from .db import Database


def corpus_status(db: Database, version: str) -> tuple[str, bool]:
    row = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version=?", (version,)
    ).fetchone()
    if row is None:
        return "unknown_corpus", False
    present = db.connection.execute(
        "SELECT 1 FROM puzzles WHERE corpus_id=? LIMIT 1", (row["id"],)
    ).fetchone()
    if present is None:
        return "empty_corpus", False
    invalid = db.connection.execute(
        "SELECT 1 FROM puzzles WHERE corpus_id=? AND rating<0 LIMIT 1", (row["id"],)
    ).fetchone()
    return "available", invalid is not None
