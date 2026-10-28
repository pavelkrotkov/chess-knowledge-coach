"""Advance one bounded page of due-item selection."""

from datetime import datetime

from .curriculum_due import due_candidate, due_page
from .curriculum_selection import select
from .db import Database


def scan_due(
    db: Database, state: dict, now: datetime, summary: dict
) -> tuple[list[dict], int, bool]:
    rows = due_page(db, now, state["due_after"], state["scan_limit"])
    selected = []
    seen = set(state["seen"])
    examined = 0
    for row in rows[: state["scan_limit"]]:
        examined += 1
        state["due_after"] = [row["due_order"], row["id"]]
        candidate = due_candidate(db, row, now)
        if candidate is not None:
            items, seen = select([candidate], state["limit"] - len(seen), summary, seen)
            selected.extend(items)
        if len(seen) >= state["limit"]:
            break
    state["seen"] = sorted(seen)
    incomplete = len(rows) > examined
    if not incomplete:
        state["phase"] = "new"
    return selected, examined, incomplete
