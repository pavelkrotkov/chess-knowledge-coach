"""Freeze and optionally match a fork cohort before writing an attempt."""

from .fork_comparison_context import context
from .fork_followup_prior import prior as previous


def attach(db, resolved, subject, corpus, attempt):
    _, version, key, binding, _ = resolved
    try:
        binding["assessment"]["context"] = context(db, version, key)
    except (ValueError, TypeError, KeyError, IndexError):
        binding["assessment"]["context"] = None
    if attempt is not None:
        evidence, expected = previous(db, subject, corpus, attempt)
        if evidence != binding["evidence_id"] or expected != binding["assessment"]["context"]:
            raise ValueError("fork comparison context changed")
