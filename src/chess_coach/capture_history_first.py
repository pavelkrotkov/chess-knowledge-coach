"""Read a bounded first-encounter history across certified capture sources."""

import time
from collections import Counter

from .capture_history_item import item
from .capture_history_select import select

SECONDS = 3.0


class HistoryDeadline(Exception):
    """Stop after the current bounded source check."""


def _category(entry):
    state = entry["status"]
    if state in {"correct", "incorrect"}:
        return ("assisted_" if entry.get("hints") else "unassisted_") + state
    return state


def report(db, subject, corpus):
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    deadline = time.monotonic() + SECONDS
    selected, limited = select(db, subject)
    found, cache = [], {}

    def check():
        if time.monotonic() >= deadline:
            raise HistoryDeadline()

    for row in reversed(selected):
        try:
            check()
            entry = item(db, row, corpus, cache, check)
            check()
        except HistoryDeadline:
            limited = True
            break
        found.append(entry)
    found.reverse()
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("capture history changed")
    return {
        "items": found,
        "counts": dict(Counter(_category(x) for x in found)),
        "limited": limited,
    }
