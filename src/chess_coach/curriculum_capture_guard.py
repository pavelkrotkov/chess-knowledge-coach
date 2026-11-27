"""Recheck the signed capture-practice snapshot under the plan's budget."""

from .curriculum_capture_file_guard import changed as files_changed
from .curriculum_capture_inputs import current
from .curriculum_priority_cursor import CAPTURE_POLICIES, COMMON_POLICY, LEGACY_CAPTURE_POLICY


def _require_scope(db, root, budget):
    if budget is None and db.connection.in_transaction:
        raise ValueError("capture practice unavailable during caller transaction")
    if budget is None or root is None:
        raise ValueError("capture practice scope unavailable")


def _reason(db, state, subject, root, budget):
    if state is None or state.get("priority_policy") not in CAPTURE_POLICIES:
        return None
    _require_scope(db, root, budget)
    from .curriculum_common_guard import check as check_common

    check_common(db, state, subject, root, budget)
    if files_changed(db, state, subject, root):
        return "capture practice changed"
    if state["priority_policy"] == COMMON_POLICY:
        return None
    # A legacy cursor with no priority contains no proof of the earlier due scan.
    if state["priority"] is None:
        return (
            "capture practice changed"
            if state["priority_policy"] == LEGACY_CAPTURE_POLICY
            else None
        )
    return _priority_reason(db, state, subject, root, budget)


def _priority_reason(db, state, subject, root, budget):
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
