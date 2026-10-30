"""Revalidate and bind original owned protection proof independently."""

from .objective_protection_contract import VERSION
from .objective_protection_source import resolve
from .recurrence_snapshot import read_snapshot
from .style_protection_binding_payload import binding
from .style_protection_schedule_budget import take
from .style_protection_schedule_guard import candidate_reason
from .style_protection_source import reference
from .style_schedule_budget import BudgetExceeded


def capture(db, learner, item):
    reason = candidate_reason(item)
    if reason:
        return None, reason
    if not take():
        return None, "source_proof_budget_exhausted"
    try:
        with read_snapshot(db):
            evidence, reason = reference(db, learner, item["position_id"])
            if evidence is None:
                return None, reason
            source = resolve(db, VERSION, str(evidence), learner)
            if reference(db, learner, item["position_id"]) != (evidence, None):
                return None, "source_changed"
            return binding(db, learner, item, evidence, source), "current"
    except BudgetExceeded:
        return None, "history_budget_exhausted"
    except (ValueError, TypeError, KeyError, IndexError):
        return None, "source_or_proof_unavailable"
