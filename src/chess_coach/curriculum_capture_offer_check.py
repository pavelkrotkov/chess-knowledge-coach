"""Validate a signed capture offer at the learning transaction boundary."""

import sqlite3

from .curriculum_capture_inputs import file_identity, observe
from .curriculum_capture_offer_scope import binding, scope
from .curriculum_window_offer_check import valid_time
from .learner_identity import normalize_identity
from .tactical_course_budget import PreviewUnavailable


def _bounded(budget, action):
    try:
        with budget.scope(snapshot=False):
            return action()
    except (OSError, sqlite3.Error, PreviewUnavailable):
        raise ValueError("capture practice offer unavailable") from None


def check(db, data, subject, source, version, key, mode, root, budget):
    from .curriculum_capture_offer import COMMON_POLICY

    if data[0] == COMMON_POLICY:
        from .curriculum_common_offer import check as check_common

        return check_common(db, data, subject, source, version, key, mode, root, budget)
    owner = normalize_identity(subject)
    scope(data, owner, source, version, key, mode)
    expected = binding(db, data[7], root, budget)
    actual, files = _bounded(budget, lambda: observe(db, owner, root, budget.check))
    if actual != expected:
        raise ValueError("capture practice offer changed")
    from .curriculum_capture_source_identity import require

    _bounded(budget, lambda: require(db, owner, data[7]["capture_sources"], budget.check))
    valid_time(data)
    return {"data": data, "subject": owner, "root": root, "files": files}


def finish(db, value, budget):
    if budget is None:
        raise ValueError("capture practice offer changed")
    if value.get("common"):
        from .curriculum_common_inputs import file_identity as current

        files = _bounded(budget, lambda: current(db, value["subject"], value["root"]))
    else:
        files = _bounded(budget, lambda: file_identity(db, value["subject"], value["root"]))
    if files != value["files"]:
        raise ValueError("capture practice offer changed")
    valid_time(value["data"])
