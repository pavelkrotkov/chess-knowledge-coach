"""Validate optional plan-window offers inside a unified start transaction."""

import time

from .curriculum_capture_offer import (
    COMMON_POLICY,
    COMMON_WINDOW_POLICY,
    CONTEXT_POLICY,
    POLICY,
    token_policy,
)
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


def prepare(db, token, root, *, opening=None):
    policy = token_policy(db, token)
    if policy not in {POLICY, CONTEXT_POLICY, COMMON_POLICY, COMMON_WINDOW_POLICY}:
        return None
    if root is None:
        raise ValueError("capture practice offer changed")
    if policy == COMMON_WINDOW_POLICY and opening is not None:
        return opening["budget"]
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SLICE_SECONDS)
    return budget
