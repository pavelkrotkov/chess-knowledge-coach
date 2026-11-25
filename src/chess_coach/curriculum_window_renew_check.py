"""Check ownership and revision before renewing a practice window."""

from .curriculum_cursor import resume_state, revision
from .curriculum_window_policy import check_policy
from .curriculum_window_renew import _renew
from .fact_fingerprint import digest
from .mastery_time import parse_utc


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
