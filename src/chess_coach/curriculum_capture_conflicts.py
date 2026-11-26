"""Continue both owned capture prompt checks across bounded schedule pages."""

from .curriculum_scheduled_query import scheduled_rows
from .curriculum_unified_reference import prompt


def _mark(options, key, matched):
    for index, (candidate, _) in enumerate(options):
        if key == candidate["prompt_key"]:
            matched |= 1 << index
    return matched


def scheduled(db, state, scan, options, check):
    remaining = max(0, state["scan_limit"] - scan["scheduled_examined"])
    rows = scheduled_rows(db, state["scheduled_after"], remaining)
    matched = state["priority"]["capture_matches"]
    for row in rows[:remaining]:
        check()
        visible, key = prompt(db, row, state["subject_hash"], check=check)
        scan["scheduled_examined"] += 1
        if visible and key is None:
            scan["scheduled_unavailable"] = True
            scan["scheduled_unavailable_item_id"] = row["id"]
            return None, "unavailable", "scheduled_prompt_unavailable"
        if visible:
            matched = _mark(options, key, matched)
        state["scheduled_after"] = row["id"]
    check()
    state["priority"]["capture_matches"] = matched
    if len(rows) > remaining:
        scan["scheduled_incomplete"] = True
        return None, "deferred", "scheduled_scan_incomplete"
    return (
        {
            candidate["prompt_key"]
            for index, (candidate, _) in enumerate(options)
            if matched & (1 << index)
        },
        None,
        None,
    )
