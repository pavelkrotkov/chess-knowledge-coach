"""Join a verified repeated opening branch to current fork observations."""

import sqlite3

from .opening_fork_nomination_join import join
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline


def nomination(db, root, learner, report):
    branch = report.get("branch")
    if branch is None:
        return {"status": "withheld", "reason": "repeated_branch_unavailable"}
    exemplar = branch["exemplar"]
    games = [item for item in branch["games"] if item["played_uci"] == exemplar["played_uci"]]
    if len(games) < 2:
        return {"status": "withheld", "reason": "same_branch_not_repeated"}
    try:
        return join(db, root, learner, report, branch, games)
    except (
        sqlite3.Error,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        TimeoutError,
        PreviewUnavailable,
        PreviewDeadline,
    ):
        return {"status": "withheld", "reason": "source_or_deadline"}
