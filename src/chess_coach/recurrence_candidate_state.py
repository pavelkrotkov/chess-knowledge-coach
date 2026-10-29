"""Check supported recurrence source markers and family currentness."""

from .discovery_contract import MAPPER as DISCOVERY_MAPPER
from .fork_contract import MAPPER as FORK_MAPPER
from .fork_defense_contract import MAPPER as DEFENSE_MAPPER
from .king_safety_probe import state as king_state
from .material_policy import MAPPER as MATERIAL_MAPPER
from .recurrence_family_policy import family_ok
from .recurrence_marker import material_state
from .recurrence_material_policy import material_ok
from .recurrence_pin_policy import PIN_FAMILIES, marker_state


def _structure_state(db, row, check):
    value = check(db, row["position_id"], row["subject"])
    return {"current": "current", "needed": "stale"}.get(value, "currentness unavailable")


def source_state(db, row, fact, parts, structure_state, rook_state):
    if row["mapping_producer"] == MATERIAL_MAPPER:
        return material_state(db, row, fact, parts) if material_ok(row, fact) else "unsupported"
    if not family_ok(row, fact):
        return "unsupported"
    checks = {
        "king-safety-lesson-mapper": king_state,
        "rook-plan-lesson-mapper": rook_state,
        "pawn-structure-lesson-mapper": structure_state,
    }
    if row["mapping_producer"] in checks:
        return _structure_state(db, row, checks[row["mapping_producer"]])
    if row["mapping_producer"] in {FORK_MAPPER, DEFENSE_MAPPER, DISCOVERY_MAPPER, *PIN_FAMILIES}:
        return marker_state(db, row, fact, parts)
    return "currentness unverified"
