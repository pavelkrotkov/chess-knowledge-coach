"""Renew a signed plan window without losing offered work."""

from .curriculum_cursor import new_state
from .curriculum_priority_cursor import inherit
from .curriculum_window_reoffer import history
from .curriculum_window_scope import create


def _renew(db, value, learner, version, scan_limit, now, minutes, budget, *, capture_changed=False):
    old = value["state"]
    changed, seen, new_seen = history(db, value, budget, force_changed=capture_changed)
    limit = min(50, len(seen) + value["page_limit"])
    if len(seen) >= limit:
        raise ValueError("practice window plan limit reached; start a new plan")
    refreshed = changed or old["as_of"] != now.isoformat()
    if refreshed:
        state = inherit(old, new_state(db, learner, version, limit, scan_limit, now))
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
