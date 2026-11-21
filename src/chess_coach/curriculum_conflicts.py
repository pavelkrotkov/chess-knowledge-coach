"""Bounded cross-corpus checks for already scheduled prompt positions."""

from .curriculum_scheduled_query import scheduled_rows
from .curriculum_unified_reference import prompt as source_prompt
from .db import Database


def scheduled_page(
    db: Database, prompt_key: str, after: int, limit: int, subject_hash: str
) -> tuple[bool, int, bool, int, int | None]:
    rows = scheduled_rows(db, after, limit)
    scanned = 0
    for row in rows[:limit]:
        scanned += 1
        after = row["id"]
        visible, scheduled_prompt = source_prompt(db, row, subject_hash)
        if not visible:
            continue
        if scheduled_prompt is None:
            return False, after, False, scanned, row["id"]
        if scheduled_prompt == prompt_key:
            return True, after, False, scanned, None
    return False, after, len(rows) > limit, scanned, None
