"""Bind certificate publication before the first due observation."""

from .capture_certificate_paths import watch
from .curriculum_priority_cursor import CAPTURE_POLICY
from .fact_fingerprint import canonical, digest
from .opening_study_source import fingerprint


def current(db, subject, root):
    return digest(canonical(fingerprint(watch(db, root, subject))))


def initialize(db, state, subject, budget):
    if state.get("priority_policy") != CAPTURE_POLICY:
        return
    if budget is None or budget.project_root is None:
        raise ValueError("capture practice scope unavailable")
    actual = current(db, subject, budget.project_root)
    if state["capture_files"] is None:
        state["capture_files"] = actual
    elif state["capture_files"] != actual:
        raise ValueError("capture practice changed; restart the plan")


def changed(db, state, subject, root):
    return state["priority_policy"] == CAPTURE_POLICY and state["capture_files"] != current(
        db, subject, root
    )


def available(db, subject, budget):
    from .capture_certificate_store import location

    return bool(budget and location(db, budget.project_root, subject))
