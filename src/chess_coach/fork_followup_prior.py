"""Resolve a current first unassisted fork result and its immutable cohort."""

import json

from .fork_comparison_context import context
from .fork_followup_first import first
from .fork_history_item import item
from .mastery_time import parse_utc
from .opening_queue_budget import BrowserBudget
from .related_fork_assessment_scope import is_source
from .tactical_course_budget import PreviewUnavailable


def _as_of(row, result, as_of):
    if as_of is None:
        return
    cutoff, started, answered = map(
        parse_utc, (as_of, row["started_at"], result.get("answered_at"))
    )
    if cutoff is None or started is None or answered is None:
        raise ValueError("fork assessment chronology unavailable")
    if not started <= answered <= cutoff:
        raise ValueError("fork assessment chronology unavailable")


def _prior(db, subject, corpus, attempt, check, *, as_of=None):
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE subject=? AND attempt_id=?", (subject, attempt)
    ).fetchone()
    if row is None or not is_source(row) or row["source_version"] != corpus:
        raise ValueError("fork assessment unavailable")
    first(db, subject, row)
    # Replay the existing immutable event and proof record; an unresolved,
    # assisted, or no-longer-current result cannot seed a comparison.
    result = item(db, row, corpus, check)
    _as_of(row, result, as_of)
    if (result["status"], result.get("hints"), result.get("reveals")) != ("correct", 0, 0):
        raise ValueError("fork assessment is not current and unassisted")
    binding = json.loads(row["provenance_json"])["related_fork"]
    if (binding.get("motif"), binding.get("operation"), binding.get("pattern_cued")) != (
        "fork",
        "execute",
        True,
    ):
        raise ValueError("fork cue unavailable")
    expected = binding["assessment"].get("context")
    if expected is None or expected != context(db, corpus, row["source_key"]):
        raise ValueError("fork comparison context unavailable")
    return binding["evidence_id"], expected


def prior(db, subject, corpus, attempt):
    if not isinstance(attempt, str) or not attempt or len(attempt) > 128 or not attempt.isascii():
        raise ValueError("fork assessment unavailable")
    try:
        budget = BrowserBudget(db)
        with budget.scope(snapshot=False):
            return _prior(db, subject, corpus, attempt, budget.check)
    except PreviewUnavailable:
        raise ValueError("fork assessment unavailable") from None
