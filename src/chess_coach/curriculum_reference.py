"""Decode only unambiguous versioned puzzle references."""

import json

from .curriculum_candidates import verified_candidate
from .db import Database


def reference(value: str) -> tuple[str, str] | None:
    try:
        ref = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(ref, list) or len(ref) != 2 or not all(isinstance(x, str) and x for x in ref):
        return None
    return ref[0], ref[1]


def referenced_candidate(db: Database, source_ref: str) -> dict | None:
    ref = reference(source_ref)
    if ref is None:
        return None
    row = db.connection.execute(
        """SELECT p.*, c.version FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND p.puzzle_id=?""",
        ref,
    ).fetchone()
    return verified_candidate(row) if row is not None else None
