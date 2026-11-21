"""Keyset-page due puzzle tasks before new material."""

from datetime import datetime

from .curriculum_due_fetch import fetch as _fetch
from .curriculum_unified_reference import candidate as source_candidate
from .db import Database
from .mastery_time import parse_utc


def due_page(db: Database, now: datetime, after: list | None, limit: int):
    count = limit + 1
    if after is None:
        return _fetch(db, now, "", [], count)
    rows = _fetch(db, now, " AND julianday(due)=? AND id>?", after, count, order="id")
    if len(rows) < count:
        rows.extend(_fetch(db, now, " AND julianday(due)>?", [after[0]], count - len(rows)))
    return rows


def due_candidate(db: Database, row, now: datetime, subject_hash: str) -> dict | None:
    due = parse_utc(row["due"])
    if due is None or due > now:
        return None
    _, candidate = source_candidate(db, row, subject_hash)
    if candidate is None:
        return None
    return {**candidate, "kind": "due", "item_id": row["id"], "due": due.isoformat()}
