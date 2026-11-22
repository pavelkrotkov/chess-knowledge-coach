"""Advance a bounded public-mate keyset and its scheduled conflict check."""

from .curriculum_capture_conflict import check_conflicts
from .curriculum_public_source import candidate, rows, version
from .public_mate_contract import OBJECTIVE


def _attempt(db, state, subject, counts, check, source_version, key):
    pending = state["public_pending"]
    try:
        item, status = candidate(db, subject, source_version, key)
    except (ValueError, TypeError, KeyError, IndexError):
        check()
        if pending is not None:
            raise ValueError("public source changed; restart the plan") from None
        state["public_status"] = "unavailable"
        return None
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


def _pending(db, state, subject, counts, check):
    collection, key = state["public_after"]
    source_version = version(db, collection)
    if source_version is None:
        raise ValueError("public source changed; restart the plan")
    result = _attempt(db, state, subject, counts, check, source_version, key)
    if result is None:
        raise ValueError("public source changed; restart the plan")
    return result


def scan(db, state, subject, counts, check):
    if db.compat32:
        state["public_status"] = "learning_unavailable"
        return [], "learning_unavailable", None, None
    if check is None:
        state["public_status"] = "unavailable"
        return [], "unavailable", None, None
    if state["public_pending"] is not None:
        return _pending(db, state, subject, counts, check)
    remaining = max(0, state["scan_limit"] - counts.get("public_examined", 0))
    batch = rows(db, state["public_after"] or [0, ""], remaining)
    for row in batch[:remaining]:
        check()
        state["public_after"] = [row["id"], row["task_id"]]
        state["public_examined"] += 1
        counts["public_examined"] = counts.get("public_examined", 0) + 1
        if row["objective"] != OBJECTIVE:
            continue
        result = _attempt(db, state, subject, counts, check, row["version"], row["task_id"])
        if result is not None and (result[0] or result[2]):
            return result
    if len(batch) > remaining:
        state["public_status"] = "deferred"
        return [], "deferred", "public_scan_incomplete", None
    if state["public_status"] not in {"provided", "exposure_unknown", "unavailable"}:
        state["public_status"] = "exhausted"
    return [], state["public_status"], None, None
