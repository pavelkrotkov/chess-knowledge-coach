"""Bound and describe the new-material scan."""

from .curriculum_new import new_candidates
from .db import Database


def new_items(
    db: Database, version: str, scan_limit: int, due_more: bool, selected: int, limit: int
) -> tuple[list[dict], bool, int, str]:
    row = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version=?", (version,)
    ).fetchone()
    if row is None:
        return [], False, 0, "unknown_corpus"
    present = db.connection.execute(
        "SELECT 1 FROM puzzles WHERE corpus_id=? LIMIT 1", (row["id"],)
    ).fetchone()
    if present is None:
        return [], False, 0, "empty_corpus"
    if due_more or selected >= limit:
        return [], False, 0, "not_scanned"
    candidates, more, scanned = new_candidates(db, version, scan_limit)
    state = "scan_incomplete" if more else ("scanned" if candidates else "no_new_candidates")
    return candidates, more, scanned, state
