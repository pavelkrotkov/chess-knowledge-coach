"""Read a bounded private history of first-encounter fork assessments."""

import time
from collections import Counter

from .capture_history_select import select
from .fork_history_item import item
from .opening_queue_budget import BrowserBudget
from .related_fork_assessment_scope import is_source
from .tactical_course_budget import PreviewUnavailable

SECONDS = 3.0


def report(db, subject, corpus):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    try:
        with budget.scope(snapshot=False):
            selected, limited = select(db, subject, predicate=is_source)
    except PreviewUnavailable:
        selected, limited = [], True
    found = []
    for row in reversed(selected):
        try:
            with budget.scope(snapshot=False):
                entry = item(db, row, corpus, budget.check)
        except PreviewUnavailable:
            limited = True
            break
        found.append(entry)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != budget.version:
        raise ValueError("fork history changed")
    return {
        "items": found,
        "counts": dict(Counter(entry["status"] for entry in found)),
        "assisted": sum(bool(entry.get("hints")) for entry in found),
        "limited": limited,
    }
