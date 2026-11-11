"""Attach only exact-exemplar scores and indexed public examples."""

import time

from .opening_explore import CHECK_LIMIT, GROUP_LIMIT
from .opening_explore_alternatives import describe
from .opening_explore_latest import hint
from .opening_explore_latest_extra import more
from .opening_explore_latest_score import attach
from .opening_queue_view import statuses
from .opening_reference_read import matches
from .tactical_course_deadline import PreviewDeadline


def enrich(db, root, learner, report):
    branch = report["branch"]
    if branch is None:
        report["partial"] |= len(report["_nominations"]) > report["groups_checked"]
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
    report["_latest_slot"] = hint(db, root, learner)
    report["_latest_candidate"] = None
    more(
        db,
        learner,
        report["_nominations"],
        report["_latest_slot"],
        report["_budget"],
        report["_cache"],
        report,
        GROUP_LIMIT,
        CHECK_LIMIT,
    )
    attach(db, root, learner, report)
    report["partial"] |= len(report["_nominations"]) > report["groups_checked"]
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != report["_version"]:
        raise ValueError("opening sample changed")
