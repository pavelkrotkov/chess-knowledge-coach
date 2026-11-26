"""Recheck the signed capture-practice snapshot under the plan's budget."""

from .curriculum_capture_inputs import current
from .curriculum_priority_cursor import CAPTURE_POLICY


def check(db, state, subject, root, budget):
    if (
        state is None
        or state.get("priority_policy") != CAPTURE_POLICY
        or state.get("priority") is None
    ):
        return
    if budget is None or root is None:
        raise ValueError("capture practice scope unavailable")
    with budget.scope(snapshot=False):
        actual = current(db, subject, root, budget.check)
        if actual != state["priority"]["capture_input"]:
            raise ValueError("capture practice changed; restart the plan")
        _sources(db, state["priority"]["capture_sources"], subject, budget.check)


def _sources(db, value, subject, check):
    if value is not None:
        from .curriculum_capture_source_identity import require

        require(db, subject, value, check)


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
