"""Match a scheduled item to its immutable versioned puzzle."""

from .db import Database
from .fact_fingerprint import canonical


def puzzle_training_ref(version: str, puzzle_id: str) -> str:
    """Stable, unambiguous source reference for a versioned puzzle."""
    return canonical([version, puzzle_id])


def training_item(db: Database, item_id: int, session):
    item = db.connection.execute("SELECT * FROM training_items WHERE id = ?", (item_id,)).fetchone()
    expected = puzzle_training_ref(session["corpus_version"], session["puzzle_id"])
    if item is None or item["source_type"] != "puzzle" or item["source_ref"] != expected:
        raise ValueError("training item does not match the versioned puzzle")
    return item
