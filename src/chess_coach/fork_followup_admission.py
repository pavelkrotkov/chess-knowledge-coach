"""Freeze and optionally match a fork cohort before writing an attempt."""

from .fork_comparison_context import context
from .fork_difficulty_selection import signed_attempt
from .fork_followup_prior import prior as previous
from .fork_followup_reference import resolve


def attach(db, resolved, expected):
    _, version, key, binding, _ = resolved
    try:
        binding["assessment"]["context"] = context(db, version, key)
    except (ValueError, TypeError, KeyError, IndexError):
        binding["assessment"]["context"] = None
    if expected is not None and expected != binding["assessment"]["context"]:
        raise ValueError("fork comparison context changed")


def reference(db, selected, subject, corpus, secret, signed, attempt, difficulty=None):
    evidence, expected = (
        previous(db, subject, corpus, attempt)
        if difficulty is None
        else (difficulty["evidence"], difficulty["expected"])
    )
    if evidence != selected[0]["provenance"]["evidence_id"]:
        raise ValueError("fork comparison source changed")
    return resolve(
        selected, secret, signed, signed_attempt(attempt, difficulty), expected
    ), expected
