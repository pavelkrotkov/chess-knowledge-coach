"""Find bounded deterministic new puzzle candidates."""

from .curriculum_candidates import verified_candidate
from .db import Database
from .training_feedback_item import puzzle_training_ref


def new_candidates(db: Database, version: str, scan_limit: int) -> tuple[list[dict], bool, int]:
    rows = db.connection.execute(
        """SELECT p.*, c.version FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? ORDER BY p.rating,p.puzzle_id LIMIT ?""",
        (version, scan_limit + 1),
    ).fetchall()
    result = []
    for row in rows[:scan_limit]:
        if _scheduled(db, version, row["puzzle_id"]):
            continue
        candidate = verified_candidate(row)
        if candidate is not None:
            result.append({**candidate, "kind": "new", "item_id": None, "due": None})
    return result, len(rows) > scan_limit, min(len(rows), scan_limit)


def _scheduled(db: Database, version: str, puzzle_id: str) -> bool:
    return (
        db.connection.execute(
            """SELECT 1 FROM training_items WHERE source_type='puzzle' AND source_ref=?
        AND skill='mate_in_one' AND operation='execute'""",
            (puzzle_training_ref(version, puzzle_id),),
        ).fetchone()
        is not None
    )
