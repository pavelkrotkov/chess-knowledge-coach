"""Bind a public source before the bounded scheduled-conflict scan."""

from .curriculum_capture_conflict import check_conflicts
from .curriculum_public_source import candidate, version


def attempt(db, state, subject, counts, check, source_version, key):
    pending = state["public_pending"]
    try:
        item, status = candidate(db, subject, source_version, key)
    except (ValueError, TypeError, KeyError, IndexError):
        check()
        item, status = None, "unavailable"
    if pending is not None and (item is None or item["binding"] != pending):
        raise ValueError("public source changed; restart the plan")
    if item is None:
        state["public_status"] = status
        return None
    if item["prompt_key"] in state["seen"]:
        return None
    result = check_conflicts(db, state, counts, check, item, None, pending_key="public_pending")
    state["phase"] = "public"
    if result[0]:
        from .curriculum_public_launch import issue

        state["public_binding"] = item["binding"]
        state["public_status"] = "offered"
        result[0][0]["prerequisite_token"] = issue(db, state, item)
    return result


def resume(db, state, subject, counts, check):
    collection, key = state["public_after"]
    source_version = version(db, collection)
    if source_version is None:
        raise ValueError("public source changed; restart the plan")
    result = attempt(db, state, subject, counts, check, source_version, key)
    if result is None:
        raise ValueError("public source changed; restart the plan")
    return result
