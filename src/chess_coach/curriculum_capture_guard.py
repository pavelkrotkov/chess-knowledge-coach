"""Recheck the signed capture-practice snapshot under the plan's budget."""

from .curriculum_capture_inputs import current
from .curriculum_priority_cursor import CAPTURE_POLICY


def _reason(db, state, subject, root, budget):
    if (
        state is None
        or state.get("priority_policy") != CAPTURE_POLICY
        or state.get("priority") is None
    ):
        return None
    if budget is None or root is None:
        raise ValueError("capture practice scope unavailable")
    with budget.scope(snapshot=False):
        actual = current(db, subject, root, budget.check)
        if actual != state["priority"]["capture_input"]:
            return "capture practice changed"
        from .curriculum_capture_source_identity import changed

        if changed(db, subject, state["priority"]["capture_sources"], budget.check):
            return "capture sources changed"
    return None


def check(db, state, subject, root, budget):
    reason = _reason(db, state, subject, root, budget)
    if reason is not None:
        raise ValueError(reason + "; restart the plan")


def changed(db, state, subject, root, budget):
    return _reason(db, state, subject, root, budget) is not None


def window(db, page, subject, root, budget):
    from .curriculum_window_cursor import decode

    state = decode(db, page["window_cursor"])["state"]
    check(db, state, subject, root, budget)
    return page


def plain(db, page, state, subject, root, budget):
    from .curriculum_capture_offer_page import untimed

    check(db, state, subject, root, budget)
    untimed(db, state, page)
    return page
