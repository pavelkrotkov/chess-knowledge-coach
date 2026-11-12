"""Recheck the latest source-bound fork assessment for advisory practice."""

import json
import time

from .fork_followup_first import first
from .fork_followup_prior import _prior
from .fork_history_item import item
from .mate_assessment_rows import LIMIT, _end
from .related_fork_assessment_scope import is_source

SECONDS = 3.0


# Keep the selected lesson source exact: results for another evidence item
# cannot drive the action even when they have the same fork pattern.
def _matches(row, evidence):
    if not is_source(row):
        return False
    binding = json.loads(row["provenance_json"])["related_fork"]
    return type(binding.get("evidence_id")) is int and binding["evidence_id"] == evidence


def _ambiguous(matches, boundary):
    if not matches or matches[0]["started_at"] == boundary:
        return True
    return len(matches) == 2 and matches[0]["started_at"] == matches[1]["started_at"]


# The indexed newest window includes one boundary probe. A tied cutoff
# cannot establish whether a matching attempt was omitted.
def _candidates(db, subject, evidence, check):
    selected = _end(db, subject, "DESC")
    boundary = selected[LIMIT]["started_at"] if len(selected) > LIMIT else None
    matches = []
    for row in selected[:LIMIT]:
        check()
        try:
            if _matches(row, evidence):
                matches.append(row)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue
    return matches, boundary


# The event replay checks the complete attempt, including assistance after
# a proof. The established follow-up admission additionally checks its cohort.
def _result(db, subject, corpus, row, evidence, check):
    if row is None:
        return {"status": "unknown"}
    first(db, subject, row)
    result = item(db, row, corpus, check)
    if (result.get("hints"), result.get("reveals")) != (0, 0):
        return {"status": "unknown"}
    if result["status"] == "correct":
        source, _ = _prior(db, subject, corpus, row["attempt_id"], check)
        if source == evidence:
            return {"status": "correct", "attempt": row["attempt_id"]}
    if result["status"] == "incorrect":
        return {"status": "incorrect"}
    return {"status": "unknown"}


def _attempt(db, subject, corpus, row, evidence, check):
    try:
        return _result(db, subject, corpus, row, evidence, check)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {"status": "unknown"}


def report(db, subject, corpus, evidence, budget):
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    with budget.scope(snapshot=False):
        matches, boundary = _candidates(db, subject, evidence, budget.check)
        for index, row in enumerate(matches):
            if _ambiguous(matches[index : index + 2], boundary):
                break
            budget.check()
            result = _attempt(db, subject, corpus, row, evidence, budget.check)
            if result["status"] != "unknown":
                return result
        return {"status": "unknown"}
