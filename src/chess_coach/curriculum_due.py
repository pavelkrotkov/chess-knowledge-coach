"""Select bounded due puzzle tasks before new material."""

from datetime import datetime

from .curriculum_candidates import verified_candidate
from .curriculum_reference import reference
from .db import Database
from .mastery_time import parse_utc


def due_candidates(db: Database, now: datetime, scan_limit: int) -> tuple[list[dict], bool, int]:
    rows = db.connection.execute(
        """SELECT id,source_ref,due FROM training_items
        WHERE source_type='puzzle' AND skill='mate_in_one' AND operation='execute'
        AND julianday(due) <= julianday(?) ORDER BY julianday(due),id LIMIT ?""",
        (now.isoformat(), scan_limit + 1),
    ).fetchall()
    result = []
    for row in rows[:scan_limit]:
        candidate = _due_candidate(db, row, now)
        if candidate is not None:
            result.append(candidate)
    return result, len(rows) > scan_limit, min(len(rows), scan_limit)


def _due_candidate(db: Database, row, now: datetime) -> dict | None:
    due = parse_utc(row["due"])
    ref = reference(row["source_ref"])
    if due is None or due > now or ref is None:
        return None
    puzzle = db.connection.execute(
        """SELECT p.*, c.version FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND p.puzzle_id=?""",
        ref,
    ).fetchone()
    if puzzle is None:
        return None
    candidate = verified_candidate(puzzle)
    if candidate is None:
        return None
    return {**candidate, "kind": "due", "item_id": row["id"], "due": due.isoformat()}
