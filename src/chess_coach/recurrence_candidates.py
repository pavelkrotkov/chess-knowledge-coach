"""Validate candidate ownership and link source state without re-running proofs."""

from .fork_contract import MAPPER as FORK_MAPPER
from .fork_defense_contract import MAPPER as DEFENSE_MAPPER
from .material_policy import MAPPER as MATERIAL_MAPPER
from .recurrence_family_policy import family_ok
from .recurrence_fork_marker import fork_state
from .recurrence_marker import material_state
from .recurrence_material_policy import material_ok
from .recurrence_policy import fact_ok, mapping_ok, ownership_ok
from .recurrence_review import review
from .recurrence_sources import linked_fact


def _state(db, row, fact, parts):
    if row["mapping_producer"] == MATERIAL_MAPPER:
        return material_state(db, row, fact, parts) if material_ok(row, fact) else "unsupported"
    if not family_ok(row, fact):
        return "unsupported"
    if row["mapping_producer"] in {FORK_MAPPER, DEFENSE_MAPPER}:
        return fork_state(db, row, fact, parts)
    return "currentness unverified"


def candidate(db, row, game, parts):
    decision = game["decisions"].get(row["position_id"])
    if not mapping_ok(row) or not ownership_ok(row, decision):
        return None, "ownership, mapping or review"
    fact = linked_fact(db, row)
    if not fact_ok(db, row, fact):
        return None, "linked fact"
    state = _state(db, row, fact, parts)
    if state in {"stale", "unsupported"}:
        return None, state
    return {
        "id": row["id"],
        "position_id": row["position_id"],
        "game_id": row["game_id"],
        "game_key": game["key"],
        "ply": row["ply"],
        "skill": row["skill"],
        "operation": row["operation"],
        "family": row["mapping_producer"],
        "version": fact["detector_version"],
        "outcome": row["outcome"],
        "review": review(row),
        "currentness": state,
        "decision": decision,
    }, None
