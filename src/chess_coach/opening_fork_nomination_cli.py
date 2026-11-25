"""Read the selected private database for bounded fork nominations."""

import sqlite3

from .opening_explore_view import report as explore_report
from .opening_profile_cli_db import private_database
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline


def report(root, learner, database):
    if root is None:
        raise ValueError("project root required")
    try:
        with private_database(root, learner, database=database) as db:
            found = explore_report(db, root, learner, fork=True)
            return {
                "nomination": found["fork_nomination"],
                "sample": found["sample"],
                "coverage": found["coverage"],
                "scanned": found["scanned"],
                "occurrences_checked": found["occurrences_checked"],
                "partial": found["partial"],
            }
    except (OSError, ValueError, TimeoutError, sqlite3.Error, PreviewUnavailable, PreviewDeadline):
        return {"nomination": {"status": "withheld", "reason": "source_or_deadline"}}
