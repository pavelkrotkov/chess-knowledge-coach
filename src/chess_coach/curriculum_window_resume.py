"""Bind a goal/window continuation to its current plan scope."""

from .curriculum_cursor import new_state, resume_state
from .curriculum_window_renew_check import checked_renew
from .curriculum_window_scope import create, options


def state(db, value, learner, version, limit, scan_limit, now, goal, minutes, renew, budget):
    if not value:
        from .curriculum_capture_file_guard import available
        from .curriculum_priority_cursor import upgrade

        initial = upgrade(
            new_state(db, learner, version, limit, scan_limit, now),
            capture=available(db, learner, budget),
        )
        return create(initial, goal, minutes, limit)
    selected_minutes = _scope(value, goal, minutes, renew, limit)
    state = value["state"]
    if renew:
        return checked_renew(db, value, learner, version, scan_limit, now, selected_minutes, budget)
    resume_state(db, state, learner, version, state["limit"], scan_limit, now)
    return value


def _scope(value, goal, minutes, renew, limit):
    selected_goal, selected_minutes = options(
        value["goal"] if goal is None else goal,
        value["minutes"] if minutes is None else minutes,
    )
    if selected_goal != value["goal"] or (not renew and selected_minutes != value["minutes"]):
        raise ValueError("practice window scope changed")
    if value["page_limit"] != limit:
        raise ValueError("practice window limit changed")
    return selected_minutes
