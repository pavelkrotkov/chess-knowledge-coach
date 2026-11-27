"""Bind a goal/window continuation to its current plan scope."""

from .curriculum_cursor import new_state, resume_state
from .curriculum_window_renew_check import checked_renew
from .curriculum_window_scope import create, options


def state(db, value, learner, version, limit, scan_limit, now, goal, minutes, renew, budget):
    if not value:
        from .curriculum_priority_cursor import COMMON_POLICY, available, upgrade

        capture = available(db, learner, budget)
        policy = (
            COMMON_POLICY
            if capture and limit == 1 and goal == "balanced" and minutes is None
            else None
        )
        initial = upgrade(
            new_state(db, learner, version, limit, scan_limit, now),
            capture=capture,
            policy=policy,
        )
        return create(initial, goal, minutes, limit)
    selected_minutes = _scope(value, goal, minutes, renew, limit)
    state = value["state"]
    if renew:
        return checked_renew(db, value, learner, version, scan_limit, now, selected_minutes, budget)
    resume_state(db, state, learner, version, state["limit"], scan_limit, now)
    return value


def _scope(value, goal, minutes, renew, limit):
    from .curriculum_window_policy import check_window

    check_window(value)
    selected_goal, selected_minutes = options(
        value["goal"] if goal is None else goal,
        value["minutes"] if minutes is None else minutes,
    )
    if selected_goal != value["goal"] or (not renew and selected_minutes != value["minutes"]):
        raise ValueError("practice window scope changed")
    if value["page_limit"] != limit:
        raise ValueError("practice window limit changed")
    return selected_minutes
