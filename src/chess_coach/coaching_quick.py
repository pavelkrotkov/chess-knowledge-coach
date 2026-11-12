"""Assemble a bounded partial coaching preview without broad report scans."""

import sqlite3
import time

from .coaching_quick_pair import ROW_LIMIT
from .coaching_quick_run import run_pair
from .coaching_quick_scope import label as pattern_label
from .coaching_report import VERSION
from .learner_identity import normalize_identity
from .opening_queue_budget import BrowserBudget
from .recurrence_skills import PAIRS
from .tactical_course_budget import PreviewUnavailable

TOTAL_SECONDS = 12.0


def _single_fork(pairs):
    return len(pairs) == 1 and pairs[0] == ("fork", "execute")


def report(db, subject, pairs):
    learner = normalize_identity(subject)
    if not learner:
        raise ValueError("learner unavailable")
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + TOTAL_SECONDS)
    groups, practice, deferred, limits = [], [], [], []
    scanned = 0
    practice_limited = False
    # Only this explicit scope gets a separate practice slice. Both stages
    # still share the request deadline and database version guard.
    separate_practice = _single_fork(pairs)
    for pair in pairs:
        label = pattern_label(pair)
        try:
            lessons, actions, truncated, count, practice_partial = run_pair(
                db,
                learner,
                pair,
                budget,
                separate_practice=separate_practice,
            )
        except (ValueError, TypeError, KeyError, IndexError, sqlite3.Error, PreviewUnavailable):
            deferred.append(label)
            continue
        practice_limited |= practice_partial
        groups.extend(lessons)
        practice.extend(actions)
        scanned += count
        if truncated:
            limits.append(label)
    changed = db.connection.execute("PRAGMA data_version").fetchone()[0] != budget.version
    if changed:
        groups, practice, limits = [], [], []
        scanned = 0
        deferred = [pattern_label(pair) for pair in pairs]
        practice_limited = True
    return {
        "kind": VERSION,
        "groups": groups,
        "eligible_groups": len(groups),
        "failure_limits": limits,
        "excluded": {},
        "coverage": {},
        "quick": {
            "patterns": [pattern_label(pair) for pair in pairs],
            "omitted": len(PAIRS) - len(pairs),
            "deferred": deferred,
            "scanned": scanned,
            "row_limit": ROW_LIMIT,
            "changed": changed,
            "practice_limited": practice_limited,
        },
    }, practice
