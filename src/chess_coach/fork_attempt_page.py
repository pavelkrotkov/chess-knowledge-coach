"""Read a page of prior certified fork attempts without changing history."""

import time

from .fork_attempt_cursor import pack, unpack
from .fork_attempt_read import read
from .fork_attempt_rows import rows
from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import PreviewUnavailable

SECONDS = 3.0


def page(db, subject, corpus, secret, cursor):
    before = unpack(secret, subject, cursor)
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    try:
        with budget.scope(snapshot=False):
            selected = rows(db, subject, before)
    except PreviewUnavailable:
        return {"items": [], "incomplete": True, "next_cursor": cursor}
    output, last, incomplete = read(db, selected, corpus, budget)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != budget.version:
        for entry in output:
            entry["status"] = "unavailable"
            entry.pop("hints", None)
            entry.pop("reveals", None)
        incomplete = True
    remaining = bool(last and selected[-1]["attempt_id"] != last["attempt_id"])
    return {
        "items": output,
        "incomplete": incomplete,
        "next_cursor": pack(secret, subject, last) if remaining else None,
    }
