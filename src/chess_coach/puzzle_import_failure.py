"""Mark an interrupted or corrupt import without publishing its rows."""

from .db import Database
from .puzzle_import_budget import ImportBudgetError


def fail(db: Database, corpus_id: int, reason: str) -> None:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        db.connection.execute(
            "UPDATE puzzle_corpora SET state='failed' WHERE id=? AND state='staging'", (corpus_id,)
        )
        db.connection.execute(
            "UPDATE puzzle_imports SET error=? WHERE corpus_id=?", (reason, corpus_id)
        )
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise


def record_failure(db, corpus_id, exc):
    if isinstance(exc, ImportBudgetError):
        fail(db, corpus_id, "project storage reserve reached")
        raise ImportBudgetError("project storage reserve reached") from None
    fail(db, corpus_id, "source is invalid, changed, or contains duplicate IDs")
    raise ValueError(
        "corpus import stopped; source is invalid, changed, or has duplicate IDs"
    ) from None
