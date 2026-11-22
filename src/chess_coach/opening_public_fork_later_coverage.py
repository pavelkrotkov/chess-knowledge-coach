"""Account for independently selected full-index fork coverage."""

import sqlite3
import time

from .opening_public_fork_later_observe import observe
from .opening_public_fork_stats import later
from .opening_public_proof_source import MAX_GAMES
from .opening_recent_select import rows as select_rows


def unavailable(reason):
    return {"status": "incomplete", "reason": reason, "eligible": None, "selected": None}


def branch(db, binding, move, deadline):
    if binding["control"] == "unknown":
        return unavailable("nominal_context_unknown")
    try:
        rows, context = select_rows(
            db, binding["source"]["parent"], move, binding["ply"], binding["control"]
        )
    except sqlite3.OperationalError:
        if time.monotonic() >= deadline:
            return unavailable("deadline")
        raise
    if time.monotonic() >= deadline:
        return unavailable("deadline")
    selected = rows[:MAX_GAMES]
    result = later(len(selected), context, len(rows) > MAX_GAMES)
    observe(db, selected, binding, move, deadline, result)
    if result["incomplete"] or result["interrupted"]:
        result["status"] = "incomplete"
    return result
