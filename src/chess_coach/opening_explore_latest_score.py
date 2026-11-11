"""Qualify the nominated slot only against its current exact comparison."""

import time

from .opening_explore_latest_result import result
from .opening_queue_view import statuses
from .tactical_course_deadline import PreviewDeadline


def attach(db, root, learner, report):
    branch, slot = report["_latest_candidate"], report["_latest_slot"]
    if branch is None or slot is None or time.monotonic() + 5 >= report["_deadline"]:
        return
    decision = _decision(branch["exemplar"], slot["source"])
    if decision is None:
        return
    try:
        states = statuses(
            db, root, learner, decision, deadline=report["_deadline"], with_identity=True
        )
        checked = result(db, root, learner, slot, decision, states)
        if checked and time.monotonic() < report["_deadline"]:
            report["latest_branch"] = {"branch": branch, "alternative": checked}
    except (Exception, PreviewDeadline):
        report["partial"] = True


def _decision(exemplar, source):
    choice = next(
        (item for item in exemplar["catalog"]["items"] if item["uci"] == source["alternative"]),
        None,
    )
    if choice is None:
        return None
    return {**exemplar, "catalog": {**exemplar["catalog"], "items": [choice]}}
