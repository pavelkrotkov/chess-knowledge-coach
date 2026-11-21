"""Resolve the authoritative schedule for a canonical prompt."""

from .curriculum_scheduled_query import scheduled_rows
from .curriculum_unified_reference import prompt as source_prompt
from .db import Database
from .mastery_time import parse_utc


def due_schedule_page(
    db: Database, prompt_key: str, after: int, limit: int, best: int, subject_hash: str
):
    """Find the authoritative matching schedule across bounded pages."""
    rows = scheduled_rows(db, after, limit)
    best_rank = _rank_for_id(db, best)
    examined = 0
    for row in rows[:limit]:
        examined += 1
        after = row["id"]
        visible, prompt = source_prompt(db, row, subject_hash)
        if not visible:
            continue
        if prompt is None:
            return best, after, False, examined, row["id"]
        rank = _rank(row["last_review"], row["id"])
        if prompt == prompt_key and (best_rank is None or rank > best_rank):
            best, best_rank = row["id"], rank
    return best, after, len(rows) > limit, examined, None


def _rank_for_id(db: Database, item_id: int):
    if not item_id:
        return None
    row = db.connection.execute(
        "SELECT last_review FROM training_items WHERE id=?", (item_id,)
    ).fetchone()
    if row is None:
        raise ValueError("scheduled item changed; restart the plan")
    return _rank(row["last_review"], item_id)


def _rank(reviewed_at, item_id: int):
    reviewed = parse_utc(reviewed_at)
    return (reviewed is not None, reviewed.isoformat() if reviewed else "", -item_id)
