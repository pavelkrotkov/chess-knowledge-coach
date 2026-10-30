"""Rebind a purpose comparison to its separately recorded original proof."""

import json

from .fact_fingerprint import canonical
from .style_protection_binding_payload import binding
from .style_protection_budget import take
from .style_protection_collect import collect
from .style_protection_source import load, reference


def inspect(db, learner, context, board, compared, allocation, budget, history):
    if not take(budget, "lookups"):
        return None, "report_budget_exhausted"
    evidence, reason = reference(db, learner, context["position_id"])
    if evidence is None:
        budget[reason] += 1
        return None, reason
    try:
        return _within(db, learner, context, board, compared, allocation, budget, history, evidence)
    except (ValueError, TypeError, KeyError, IndexError):
        return None, "source_or_proof_unavailable"


def _within(db, learner, context, board, compared, allocation, budget, history, evidence):
    source = load(db, learner, evidence, budget, verified_board=board, history=history)
    if source is None:
        return None, "report_budget_exhausted"
    actual = binding(db, learner, context, evidence, source)
    if canonical(actual) != canonical(json.loads(allocation["binding_json"])):
        return None, "original_source_changed"
    if not take(budget, "lookups"):
        return None, "report_budget_exhausted"
    if reference(db, learner, context["position_id"]) != (evidence, None):
        return None, "original_source_changed"
    results = collect(
        db, learner, context, board, compared, evidence, budget, source=source, history=history
    )
    return results, "current" if results is not None else "source_or_proof_unavailable"
