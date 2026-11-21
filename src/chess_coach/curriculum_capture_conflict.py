"""Continue an owned capture's bounded scheduled-prompt check."""

from .curriculum_conflicts import scheduled_page


def check_conflicts(db, state, scan, check, candidate, report, *, pending_key="capture_pending"):
    state[pending_key] = candidate["binding"]
    check()
    matched, after, more, examined, unavailable = scheduled_page(
        db,
        candidate["prompt_key"],
        state["scheduled_after"],
        state["scan_limit"] - scan["scheduled_examined"],
        state["subject_hash"],
        check=check,
    )
    check()
    scan["scheduled_examined"] += examined
    if unavailable is not None:
        scan["scheduled_unavailable"] = True
        scan["scheduled_unavailable_item_id"] = unavailable
        return [], "unavailable", "scheduled_prompt_unavailable", report
    if more:
        state["scheduled_after"] = after
        scan["scheduled_incomplete"] = True
        return [], "deferred", "scheduled_scan_incomplete", report
    state["phase"] = "new"
    state[pending_key] = None
    state["scheduled_after"] = 0
    if matched:
        return [], "already_scheduled", None, report
    state["seen"] = sorted([*state["seen"], candidate["prompt_key"]])
    return (
        [{key: value for key, value in candidate.items() if key != "binding"}],
        "offered",
        None,
        report,
    )
