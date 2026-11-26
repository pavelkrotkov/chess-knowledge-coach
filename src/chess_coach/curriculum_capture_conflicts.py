"""Check both owned capture prompts against the same bounded schedule."""

from .curriculum_scheduled_query import scheduled_rows
from .curriculum_unified_reference import prompt


def scheduled(db, state, scan, check):
    remaining = state["scan_limit"] - scan["scheduled_examined"]
    if remaining <= 0:
        return None
    rows = scheduled_rows(db, 0, remaining)
    if len(rows) > remaining:
        return None
    matched = set()
    for row in rows:
        check()
        visible, key = prompt(db, row, state["subject_hash"], check=check)
        scan["scheduled_examined"] += 1
        if visible and key is None:
            scan["scheduled_unavailable"] = True
            scan["scheduled_unavailable_item_id"] = row["id"]
            return None
        if visible:
            matched.add(key)
    check()
    return matched
