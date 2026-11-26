"""Bind certificate publication before the first due observation."""

from .capture_certificate_paths import watch
from .curriculum_priority_cursor import CAPTURE_FILE_POLICIES, CONTEXT_CAPTURE_POLICY
from .fact_fingerprint import canonical, digest
from .opening_study_source import fingerprint


def current(db, subject, root, *, context=False):
    paths = watch(db, root, subject)
    if context:
        from .capture_game_trend_paths import location

        path = location(db, root)
        if path is None:
            raise ValueError("capture report scope unavailable")
        paths.append(path)
    return digest(canonical(fingerprint(paths)))


def initialize(db, state, subject, budget):
    if state.get("priority_policy") not in CAPTURE_FILE_POLICIES:
        return
    if budget is None or budget.project_root is None:
        raise ValueError("capture practice scope unavailable")
    actual = current(
        db, subject, budget.project_root, context=state["priority_policy"] == CONTEXT_CAPTURE_POLICY
    )
    if state["capture_files"] is None:
        state["capture_files"] = actual
    elif state["capture_files"] != actual:
        raise ValueError("capture practice changed; restart the plan")


def changed(db, state, subject, root):
    return state["priority_policy"] in CAPTURE_FILE_POLICIES and state["capture_files"] != current(
        db, subject, root, context=state["priority_policy"] == CONTEXT_CAPTURE_POLICY
    )


def available(db, subject, budget):
    from .capture_certificate_store import location

    return bool(budget and location(db, budget.project_root, subject))
