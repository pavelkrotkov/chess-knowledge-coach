"""Read a bounded current history of certified protection assessments."""

import sqlite3
import time
from collections import defaultdict

from .learner_identity import normalize_identity
from .mastery_time import parse_utc
from .opening_queue_budget import BrowserBudget
from .protection_progress_groups import group
from .protection_progress_item import item
from .related_protection_objective import is_source
from .tactical_course_budget import PreviewUnavailable

LIMIT = 200
SECONDS = 30.0


def _rows(db, subject):
    return db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? AND source_type='corpus' AND objective='protect_threatened_piece'
        ORDER BY started_at DESC,attempt_id LIMIT ?""",
        (subject, LIMIT + 1),
    ).fetchall()


def _collect(db, subject, corpus, budget):
    with budget.scope(snapshot=False):
        rows = _rows(db, subject)
    # Truncation prevents establishing an ordered baseline for any group.
    limited = len(rows) > LIMIT
    items, groups = [], defaultdict(list)
    for row in reversed(rows[:LIMIT]):
        with budget.scope(snapshot=False):
            try:
                if not is_source(row):
                    continue
                when = parse_utc(row["started_at"])
                if when is None or when.isoformat() != row["started_at"]:
                    limited = True
                    raise ValueError("assessment time unavailable")
                entry = item(db, row, corpus, budget.check)
                budget.check()
                groups[entry["scope"]].append(entry)
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                entry = {
                    "attempt": row["attempt_id"],
                    "started_at": row["started_at"],
                    "status": "unavailable",
                }
            items.append(entry)
    return {
        "items": list(reversed(items)),
        "groups": [group(k, v, limited) for k, v in groups.items()],
        "limited": limited,
    }


def report(db, subject, corpus):
    subject = normalize_identity(subject)
    if not subject:
        return None
    try:
        budget = BrowserBudget(db)
        budget.expires = min(budget.expires, time.monotonic() + SECONDS)
        result = _collect(db, subject, corpus, budget)
        budget.check()
        return result
    except (
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        PreviewUnavailable,
    ):
        return None
