"""Build a goal-scoped plan inside a signed wall-clock window."""

from copy import deepcopy

from .curriculum_page import build_page
from .curriculum_window_publish import finish, offers
from .curriculum_window_resume import state
from .curriculum_window_scope import expired


def build(db, value, learner, version, limit, scan_limit, now, budget, goal, minutes, renew):
    value = state(db, value, learner, version, limit, scan_limit, now, goal, minutes, renew)
    plan_state = value["state"]
    before = deepcopy(value)
    initially_expired = expired(value)
    page = build_page(
        db, plan_state, learner, now, budget, due_only=initially_expired, window=value
    )
    offers(db, value, page)
    expired_now = initially_expired or expired(value)
    if not initially_expired and expired_now:
        value.clear()
        value.update(before)
        plan_state = value["state"]
        page = build_page(db, plan_state, learner, now, budget, due_only=True, window=value)
    return finish(db, value, plan_state, page, expired_now)
