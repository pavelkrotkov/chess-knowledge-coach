"""Find one bounded, source-verified repeated opening branch."""

import time

from .opening_explore_group import group
from .opening_explore_nomination import candidates, ranked
from .opening_explore_recent import recent
from .opening_queue_budget import BrowserBudget

GROUP_LIMIT = 3
CHECK_LIMIT = 8
TOTAL_SECONDS = 25


def explore(db, learner):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + TOTAL_SECONDS)
    with budget.scope(snapshot=False):
        rows, coverage = recent(db, learner)
    groups, scanned, incomplete = candidates(db, rows, budget)
    nominations = ranked(groups)
    report = {
        "sample": len(rows),
        "coverage": coverage,
        "scanned": scanned,
        "nominations": len(nominations),
        "groups_checked": 0,
        "occurrences_checked": 0,
        "duplicates": 0,
        "unavailable": 0,
        "deferred": 0,
        "partial": incomplete or scanned < len(rows),
        "branch": None,
        "_version": budget.version,
        "_deadline": budget.expires,
    }
    cache = {}
    for key, items in nominations[:GROUP_LIMIT]:
        if report["occurrences_checked"] >= CHECK_LIMIT or time.monotonic() >= budget.expires:
            report["partial"] = True
            break
        report["groups_checked"] += 1
        branch = group(db, learner, key, items, budget, cache, report, CHECK_LIMIT)
        if branch:
            report["branch"] = branch
            break
    if len(nominations) > report["groups_checked"]:
        report["partial"] = True
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != budget.version:
        raise ValueError("opening sample changed")
    return report
