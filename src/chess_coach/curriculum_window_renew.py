"""Renew a signed plan window without losing offered work."""

from .curriculum_cursor import new_state, resume_state, revision
from .curriculum_window_policy import check_policy
from .curriculum_window_reoffer import history
from .curriculum_window_scope import create
from .fact_fingerprint import digest
from .mastery_time import parse_utc


def _renew(db, value, learner, version, scan_limit, now, minutes, budget):
    old = value["state"]
    changed, seen, new_seen = history(db, value, budget)
    limit = min(50, len(seen) + value["page_limit"])
    if len(seen) >= limit:
        raise ValueError("practice window plan limit reached; start a new plan")
    refreshed = changed or old["as_of"] != now.isoformat()
    if refreshed:
        state = new_state(db, learner, version, limit, scan_limit, now)
        state["seen"] = seen
        state["family_turn"] = old["family_turn"]
    else:
        state = old
        state["limit"] = limit
    result = create(state, value["goal"], minutes, value["page_limit"], reset_turn=False)
    result["new_seen"] = new_seen
    result["repeat_due"] = list(new_seen) if refreshed else list(value["repeat_due"])
    result["source_refreshed"] = refreshed
    return result


def checked_renew(db, value, learner, version, scan_limit, now, minutes, budget):
    state = value["state"]
    if state["subject_hash"] != digest(learner):
        raise ValueError("practice window owner changed")
    if state["corpus_version"] != version or state["scan_limit"] != scan_limit:
        raise ValueError("practice window scope changed")
    check_policy(state)
    if state["revision"] == revision(db):
        resume_state(
            db, state, learner, version, state["limit"], scan_limit, parse_utc(state["as_of"])
        )
    return _renew(db, value, learner, version, scan_limit, now, minutes, budget)
