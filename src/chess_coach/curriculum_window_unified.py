"""Validate optional plan-window offers inside a unified start transaction."""

import time

from .curriculum_capture_offer import POLICY
from .curriculum_prerequisite_token import _decode
from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import SLICE_SECONDS


def check(
    db,
    token,
    subject,
    source_type,
    version,
    key,
    training,
    item_id,
    *,
    project_root=None,
    capture_budget=None,
):
    if token is None:
        return None
    if not training or item_id is not None:
        raise ValueError("practice window offer changed")
    from .curriculum_window_offer_check import check as check_offer

    return check_offer(
        db,
        token,
        subject,
        source_type,
        version,
        key,
        "unified",
        project_root=project_root,
        capture_budget=capture_budget,
    )


def finish(value, db, capture_budget):
    if isinstance(value, dict):
        from .curriculum_capture_offer_check import finish as finish_capture

        return finish_capture(db, value, capture_budget)
    if value is not None:
        from .curriculum_window_offer_check import valid_time

        valid_time(value)


def prepare(db, token, root):
    if token is None or _decode(db, token)[0] != POLICY:
        return None
    if root is None:
        raise ValueError("capture practice offer changed")
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SLICE_SECONDS)
    return budget
