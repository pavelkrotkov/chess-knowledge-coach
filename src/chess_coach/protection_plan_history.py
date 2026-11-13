"""Read the latest eligible assessment of one exact protection source."""

import json
import sqlite3
import time

from .fork_plan_history import _ambiguous
from .mate_assessment_rows import LIMIT, _end
from .opening_queue_budget import BrowserBudget
from .protection_plan_verify import inspect
from .related_protection_objective import is_source
from .tactical_course_budget import PreviewUnavailable

SECONDS = 3.0


def _evidence(row, corpus):
    if row["source_version"] != corpus or not is_source(row):
        return None
    value = json.loads(row["provenance_json"])["related_protection"]["evidence_id"]
    return value if type(value) is int and 0 < value < 2**63 else None


# Prefer a result tied to the selected rehearsal, then consider a separately named source.
def _group(rows, corpus, evidence, check):
    exact, other = [], []
    for row in rows:
        check()
        try:
            identity = _evidence(row, corpus)
            if identity is not None:
                (exact if identity == evidence else other).append((row, identity))
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue
    return exact, other


# A timestamp tie at the bounded history frontier cannot establish a latest result.
def _choose(db, candidates, boundary, corpus, check):
    for index, (row, evidence) in enumerate(candidates):
        nearby = [item[0] for item in candidates[index : index + 2]]
        if _ambiguous(nearby, boundary):
            break
        check()
        try:
            result = inspect(db, row, corpus, evidence)
            check()
            return result
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue
    return None


def report(db, subject, corpus, evidence):
    try:
        budget = BrowserBudget(db)
        budget.expires = min(budget.expires, time.monotonic() + SECONDS)
        with budget.scope(snapshot=False):
            rows = _end(db, subject, "DESC")
            boundary = rows[LIMIT]["started_at"] if len(rows) > LIMIT else None
            exact, other = _group(rows[:LIMIT], corpus, evidence, budget.check)
            return (
                _choose(db, exact, boundary, corpus, budget.check)
                or _choose(db, other, boundary, corpus, budget.check)
                or {"status": "unknown"}
            )
    except PreviewUnavailable:
        return {"status": "unknown"}


def optional(db, subject, corpus, protection):
    if not protection or not protection["source"]:
        return {"status": "unknown"}
    try:
        from .protection_difficulty import decorate

        result = report(db, subject, corpus, protection["source"]["evidence_id"])
        return decorate(db, subject, corpus, result)
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        return {"status": "unknown"}
