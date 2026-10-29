"""Validate candidate ownership and link source state without re-running proofs."""

from .pawn_structure_probe import state as structure_state
from .recurrence_candidate_state import source_state
from .recurrence_candidate_value import value
from .recurrence_policy import fact_ok, mapping_ok, ownership_ok
from .recurrence_sources import linked_fact
from .rook_plan_probe import state as rook_state


def candidate(db, row, game, parts):
    decision = game["decisions"].get(row["position_id"])
    if not mapping_ok(row) or not ownership_ok(row, decision):
        return None, "ownership, mapping or review"
    fact = linked_fact(db, row)
    if not fact_ok(db, row, fact):
        return None, "linked fact"
    state = source_state(db, row, fact, parts, structure_state, rook_state)
    if state in {"stale", "unsupported", "currentness unavailable"}:
        return None, state
    return value(row, fact, game, decision, state), None
