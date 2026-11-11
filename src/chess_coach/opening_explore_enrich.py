"""Attach only exact-exemplar scores and indexed public examples."""

import time

from .opening_explore_alternatives import describe
from .opening_explore_latest_score import attach
from .opening_queue_view import statuses
from .opening_reference_read import matches
from .tactical_course_deadline import PreviewDeadline


def enrich(db, root, learner, report):
    branch = report["branch"]
    if branch is None:
        return
    exemplar = branch["exemplar"]
    branch["references"] = matches(root, learner, branch["position"])
    states = {}
    if time.monotonic() + 5 < report["_deadline"]:
        try:
            states = statuses(db, root, learner, exemplar, deadline=report["_deadline"])
        except (Exception, PreviewDeadline):
            report["partial"] = True
    else:
        report["partial"] = True
    if time.monotonic() >= report["_deadline"]:
        states = {}
        report["partial"] = True
    branch["alternatives"] = describe(exemplar, states)
    attach(db, root, learner, report)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != report["_version"]:
        raise ValueError("opening sample changed")
