"""Compare bounded, current first-encounter knight-fork practice samples."""

import time

from .fork_progress_compare import comparison
from .fork_progress_select import select
from .mate_assessment_compare import SAMPLE
from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import PreviewUnavailable

SECONDS = 30.0


def report(db, subject, corpus):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    result = {"status": "incomplete", "largest": 0}
    try:
        groups, limited, window_limited = select(db, subject, corpus, budget)
        result["window_limited"] = window_limited
        result["largest"] = max((len(group) for group in groups), default=0)
        if not limited:
            result["status"] = "sparse"
            eligible = [group for group in groups if len(group) >= 2 * SAMPLE]
            if eligible:
                group = max(eligible, key=lambda value: value[-1]["started_at"])
                result.update(comparison(db, group, corpus, budget))
    except PreviewUnavailable:
        result = {"status": "incomplete", "largest": 0}
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != budget.version:
        return {"status": "incomplete", "largest": 0}
    return result
