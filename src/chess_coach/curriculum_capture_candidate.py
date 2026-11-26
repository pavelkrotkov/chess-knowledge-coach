"""Bind a resumed capture candidate before checking scheduled conflicts."""

from .curriculum_capture_conflict import check_conflicts
from .curriculum_capture_source import read


def check_candidate(db, state, subject, scan, check):
    from .curriculum_priority_cursor import CAPTURE_POLICIES

    if state.get("priority_policy") in CAPTURE_POLICIES:
        from .curriculum_capture_choice import select

        return select(db, state, subject, scan, check)
    candidate, status, report = read(db, subject, state["corpus_version"], check)
    pending = state["capture_pending"]
    if pending is not None and (candidate is None or candidate["binding"] != pending):
        raise ValueError("capture source changed; restart the plan")
    if candidate is None or candidate["prompt_key"] in state["seen"]:
        state["phase"] = "new"
        return [], status if candidate is None else "duplicate", None, report
    return check_conflicts(db, state, scan, check, candidate, report)
