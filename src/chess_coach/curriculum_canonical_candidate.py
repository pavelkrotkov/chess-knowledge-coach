"""Bind a canonical task before the scheduled-conflict scan."""

from .curriculum_canonical_source import candidate
from .curriculum_capture_conflict import check_conflicts


def attempt(db, state, subject, counts, check, choice, current):
    pending = state["canonical_pending"]
    try:
        item, status = candidate(db, subject, choice, current)
    except (ValueError, TypeError, KeyError, IndexError):
        check()
        item, status = None, "unavailable"
    if pending is not None and (item is None or item["binding"] != pending):
        raise ValueError("canonical source changed; restart the plan")
    if item is None:
        state["canonical_status"] = status
        return None
    if item["prompt_key"] in state["seen"]:
        return None
    result = check_conflicts(db, state, counts, check, item, None, pending_key="canonical_pending")
    state["phase"] = "canonical"
    if result[0]:
        from .curriculum_canonical_launch import issue

        state["canonical_binding"] = item["binding"]
        state["canonical_status"] = "offered"
        result[0][0]["prerequisite_token"] = issue(db, state, item)
    return result
