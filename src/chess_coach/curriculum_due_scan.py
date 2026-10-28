"""Advance one bounded page of due-item selection."""

from datetime import datetime

from .curriculum_due import due_candidate, due_page
from .curriculum_due_schedule import check_schedule, eligible
from .curriculum_selection import select
from .db import Database


def scan_due(db: Database, state: dict, now: datetime, summary: dict, scan: dict):
    rows = due_page(db, now, state["due_after"], state["scan_limit"])
    selected = []
    seen = set(state["seen"])
    examined = 0
    reason = None
    for row in rows[: state["scan_limit"]]:
        examined += 1
        candidate = due_candidate(db, row, now)
        if eligible(candidate, seen):
            reason = check_schedule(db, state, candidate, scan)
            if reason:
                break
            if state["scheduled_best"] == row["id"]:
                items, seen = select([candidate], state["limit"] - len(seen), summary, seen)
                selected.extend(items)
            state["scheduled_best"] = 0
            state["scheduled_after"] = 0
        state["due_after"] = [row["due_order"], row["id"]]
        if len(seen) >= state["limit"]:
            break
    state["seen"] = sorted(seen)
    incomplete = reason is not None or len(rows) > examined
    if not incomplete:
        state["phase"] = "new"
    return selected, examined, incomplete, reason
