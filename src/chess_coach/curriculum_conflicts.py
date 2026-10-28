"""Bounded cross-corpus checks for already scheduled prompt positions."""

from .curriculum_prompt_reference import referenced_prompt
from .db import Database


def scheduled_page(
    db: Database, prompt_key: str, after: int, limit: int
) -> tuple[bool, int, bool, int, int | None]:
    rows = db.connection.execute(
        """SELECT id,source_ref FROM training_items INDEXED BY idx_curriculum_scheduled
        WHERE id>? AND source_type='puzzle' AND skill='mate_in_one' AND operation='execute'
        ORDER BY id LIMIT ?""",
        (after, limit + 1),
    ).fetchall()
    scanned = 0
    for row in rows[:limit]:
        scanned += 1
        after = row["id"]
        scheduled_prompt = referenced_prompt(db, row["source_ref"])
        if scheduled_prompt is None:
            return False, after, False, scanned, row["id"]
        if scheduled_prompt == prompt_key:
            return True, after, False, scanned, None
    return False, after, len(rows) > limit, scanned, None
