"""Bind an untimed comparison before due observation and on continuation."""

from .curriculum_capture_inputs import current as capture_inputs
from .curriculum_common_cursor import bind_input
from .curriculum_common_inputs import file_identity, observe
from .curriculum_common_practice import observe as practice_inputs
from .curriculum_cursor import revision
from .curriculum_priority_cursor import COMMON_POLICY
from .tactical_course_budget import SLICE_SECONDS


def check(db, state, subject, root, budget):
    if state is None or state.get("priority_policy") != COMMON_POLICY:
        return
    if budget is None or root is None:
        raise ValueError("common practice scope unavailable")
    budget.expires = min(budget.expires, budget.common_started + SLICE_SECONDS)
    with budget.scope(snapshot=False):
        bundle = getattr(budget, "common_choice", None)
        if bundle is not None:
            recheck(db, subject, state["corpus_version"], root, bundle, budget.check)
            return
        _initial(db, state, subject, root, budget)


def _initial(db, state, subject, root, budget):
    actual, bundle = observe(
        db, subject, state["corpus_version"], root, state["as_of"], budget.check
    )
    bind_input(state, actual)
    budget.common_choice = bundle


def recheck(db, subject, corpus, root, bundle, check):
    check()
    if (
        file_identity(db, subject, root) != bundle["files"]
        or revision(db) != bundle["revision"]
        or capture_inputs(db, subject, root, check) != bundle["capture"]
        or practice_inputs(db, subject, corpus, bundle["attempts"], check) != bundle["practice"]
    ):
        raise ValueError("common practice changed; restart the plan")
