"""Renew a signed plan window while retaining checked positions."""

from .curriculum_cursor import new_state, resume_state, revision
from .curriculum_window_scope import create
from .fact_fingerprint import digest


def _renew(db, value, learner, version, scan_limit, now, minutes):
    old = value["state"]
    limit = min(50, len(old["seen"]) + value["page_limit"])
    if len(old["seen"]) >= limit:
        raise ValueError("practice window plan limit reached; start a new plan")
    if old["revision"] != revision(db):
        state = new_state(db, learner, version, limit, scan_limit, now)
        state["seen"] = list(old["seen"])
        state["family_turn"] = old["family_turn"]
    else:
        state = old
        state["limit"] = limit
    return create(state, value["goal"], minutes, value["page_limit"])


def checked_renew(db, value, learner, version, scan_limit, now, minutes):
    state = value["state"]
    if state["subject_hash"] != digest(learner):
        raise ValueError("practice window owner changed")
    if state["corpus_version"] != version or state["scan_limit"] != scan_limit:
        raise ValueError("practice window scope changed")
    if state["as_of"] != now.isoformat():
        raise ValueError("practice window time changed")
    if state["revision"] == revision(db):
        resume_state(db, state, learner, version, state["limit"], scan_limit, now)
    return _renew(db, value, learner, version, scan_limit, now, minutes)
