"""Resolve an uncertain opening Study create without publishing the course."""

import re

from .course_preview import preview_hash
from .opening_queue_lock import lock as opening_lock
from .opening_study_freeze import _stamp
from .opening_study_session import _paths
from .study_authorization import require_scopes
from .study_destination import destination
from .study_remote import StudyError
from .study_session import _publish, locked
from .tactical_export_input import _read
from .tactical_study_ledger import validate


# An uncertain create occurs before any chapter upload. Only that state can
# safely enter destination(), whose other branch would create a new Study.
def _pending(state):
    return (
        state.get("study") is None
        and state.get("create_pending") is True
        and state.get("complete") is False
        and re.fullmatch(r"Chess coaching [0-9a-f]{16}", state.get("marker", ""))
    )


def _reconcile(remote, path, course):
    state = _read(path)
    body = course["course"]
    if (
        state.get("course_sha256") != course.get("course_sha256")
        or course.get("course_sha256") != preview_hash(body)
        or not _pending(state)
    ):
        raise StudyError("opening Study intent cannot be reconciled")
    validate(state, body["chapters"])
    if any(value != "new" for value in state["chapters"]):
        raise StudyError("opening Study intent cannot be reconciled")
    account = remote.account()
    require_scopes(remote)
    destination(remote, path, state, account)


def reconcile_locked(root, version):
    _, _, planning, database = _paths(root, version)
    with locked(database, planning), opening_lock(planning):
        path = planning / f"opening-study-{version}-intent.json"
        frozen = planning / f"opening-study-{version}-course.json"
        # The retained snapshot establishes intent identity; current source data
        # may have changed since the uncertain create and must not be uploaded.
        course = _read(frozen)
        _stamp(frozen, course)
        if (
            course["course"].get("kind") != "opening-study-course-v1"
            or course["course"].get("preview_version") != version
        ):
            raise StudyError("opening course version differs")
        return _publish(database, path, course, action=_reconcile)
