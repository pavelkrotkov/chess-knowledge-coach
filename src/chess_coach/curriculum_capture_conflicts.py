"""Continue both owned capture prompt checks across bounded schedule pages."""

from .curriculum_scheduled_query import scheduled_rows
from .curriculum_unified_reference import prompt


def _mark(options, key, matched):
    for index, (candidate, _) in enumerate(options):
        if key == candidate["prompt_key"]:
            matched |= 1 << index
    return matched


def scheduled(db, state, scan, options, check, *, common=False):
    remaining = max(0, state["scan_limit"] - scan["scheduled_examined"])
    rows = scheduled_rows(db, state["scheduled_after"], remaining)
    if common:
        progress, mask_key = state["common"], "matches"
    else:
        progress, mask_key = state["priority"], "capture_matches"
    matched = progress[mask_key]
    for row in rows[:remaining]:
        check()
        visible, prompt_key = prompt(db, row, state["subject_hash"], check=check)
        scan["scheduled_examined"] += 1
        if visible:
            if prompt_key is None:
                scan["scheduled_unavailable"] = True
                scan["scheduled_unavailable_item_id"] = row["id"]
                return None, "unavailable", "scheduled_prompt_unavailable"
            matched = _mark(options, prompt_key, matched)
        state["scheduled_after"] = row["id"]
        progress[mask_key] = matched
    check()
    progress[mask_key] = matched
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
