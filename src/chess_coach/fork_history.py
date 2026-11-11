"""Read a bounded private history of first-encounter fork assessments."""

import time
from collections import Counter

from .capture_history_select import select
from .fork_history_item import item
from .related_fork_assessment_scope import is_source

SECONDS = 3.0


class HistoryDeadline(Exception):
    """Stop after the current bounded source check."""


def report(db, subject, corpus):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    deadline = time.monotonic() + SECONDS
    selected, limited = select(db, subject, predicate=is_source)
    found = []

    def check():
        if time.monotonic() >= deadline:
            raise HistoryDeadline()

    for row in reversed(selected):
        try:
            check()
            entry = item(db, row, corpus, check)
            check()
        except HistoryDeadline:
            limited = True
            break
        found.append(entry)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("fork history changed")
    return {
        "items": found,
        "counts": dict(Counter(entry["status"] for entry in found)),
        "assisted": sum(bool(entry.get("hints")) for entry in found),
        "limited": limited,
    }
