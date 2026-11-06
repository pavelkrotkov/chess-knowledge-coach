"""Revalidate only two selected capture cohorts, with a cooperative budget."""

import time

from .capture_history_first import HistoryDeadline
from .capture_history_item import item

SECONDS = 30.0


def verify(db, rows, corpus):
    deadline = time.monotonic() + SECONDS
    cache, output = {}, []

    def check():
        if time.monotonic() >= deadline:
            raise HistoryDeadline()

    for row in rows:
        try:
            check()
            entry = item(db, row, corpus, cache, check)
            check()
        except HistoryDeadline:
            return output, False
        entry.setdefault("hints", None)
        entry.setdefault("reveals", None)
        status = entry["status"]
        output.append(
            {
                **entry,
                "current": status in {"correct", "incorrect"},
                "outcome": "verified" if status == "correct" else status,
            }
        )
    return output, True
