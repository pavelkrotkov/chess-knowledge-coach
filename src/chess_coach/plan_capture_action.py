"""Short, advisory capture guidance for the first daily-plan page."""

import sqlite3
import time

from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable
from .unified_sources import resolve_source


def recommendation(db, subject, corpus):
    from .capture_plan import report

    try:
        deadline = time.monotonic() + SLICE_SECONDS

        def check():
            if time.monotonic() >= deadline:
                raise PreviewUnavailable("request deadline reached")

        with BrowserBudget(db).scope(snapshot=False):
            result = report(db, subject, corpus, check=check)
        source = result["source"]
        if not source or source["games"] < 2 or not isinstance(result["history"], dict):
            return None
        return result
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        return None


def admissible(db, subject, corpus):
    capture = recommendation(db, subject, corpus)
    if not capture:
        return None
    try:
        source = capture["source"]
        with BrowserBudget(db).scope(snapshot=False):
            resolve_source(db, "own-game", source["version"], source["key"], subject=subject)
        return capture
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        return None
