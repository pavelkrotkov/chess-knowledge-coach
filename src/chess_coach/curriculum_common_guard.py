"""Bind an untimed comparison before due observation and on continuation."""

from .curriculum_common_inputs import observe, recheck
from .curriculum_priority_cursor import COMMON_POLICY, CONTEXT_CAPTURE_POLICY
from .tactical_course_budget import SLICE_SECONDS


def check(db, state, subject, root, budget):
    if state is None or state.get("priority_policy") != COMMON_POLICY:
        return
    if budget is None or root is None:
        raise ValueError("common practice scope unavailable")
    if not hasattr(budget, "previous_expiry"):
        budget.previous_expiry = budget.expires
        budget.expires = min(budget.expires, budget.common_started + SLICE_SECONDS)
    with budget.scope(snapshot=False):
        bundle = getattr(budget, "common_choice", None)
        if bundle is not None:
            recheck(db, subject, state["corpus_version"], root, bundle, budget.check)
            return
        _initial(db, state, subject, root, budget)


def _initial(db, state, subject, root, budget):
    try:
        actual, bundle = observe(
            db, subject, state["corpus_version"], root, state["as_of"], budget.check
        )
    except ValueError as error:
        if state["common_input"] is not None or str(error) not in {
            "practice source unavailable",
            "capture objective unavailable",
            "capture history unavailable",
            "capture source unavailable",
            "capture target unavailable",
            "fork source unavailable",
            "fork objective unavailable",
        }:
            raise
        budget.check()
        state["priority_policy"] = CONTEXT_CAPTURE_POLICY
        state.pop("common_input")
        state.pop("common")
        budget.expires = budget.previous_expiry
        return
    if state["common_input"] is None:
        state["common_input"] = actual
    elif state["common_input"] != actual:
        raise ValueError("common practice changed; restart the plan")
    budget.common_choice = bundle
