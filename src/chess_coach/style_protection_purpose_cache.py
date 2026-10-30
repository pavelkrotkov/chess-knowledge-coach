"""Reuse only validated original protection sources inside one report snapshot."""

from .fact_fingerprint import canonical
from .style_protection_binding_payload import binding
from .style_protection_budget import take
from .style_protection_source import load, reference


def source(db, learner, context, board, budget, history, cache):
    key = (context["game_id"], context["position_id"])
    if key in cache:
        return cache[key], None
    value, reason = _resolve(db, learner, context, board, budget, history)
    if value is not None:
        cache[key] = value
    return value, reason


def _resolve(db, learner, context, board, budget, history):
    if not take(budget, "lookups"):
        return None, "report_budget_exhausted"
    evidence, reason = reference(db, learner, context["position_id"])
    if evidence is None:
        budget[reason] += 1
        return None, reason
    found = load(db, learner, evidence, budget, verified_board=board, history=history)
    if found is None:
        return None, "report_budget_exhausted"
    actual = canonical(binding(db, learner, context, evidence, found))
    if not take(budget, "lookups"):
        return None, "report_budget_exhausted"
    if reference(db, learner, context["position_id"]) != (evidence, None):
        return None, "original_source_changed"
    return (evidence, found, actual), None
