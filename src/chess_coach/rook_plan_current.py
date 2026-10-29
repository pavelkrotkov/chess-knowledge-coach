"""Verify published rook observations without rerunning their chess analysis."""

from .material_opportunity_links import valid_link
from .rook_plan_mapping import MAPPER
from .rook_plan_probe import state


def currentness(db, evidence, *, _history=None):
    if evidence["mapping_producer"] != MAPPER:
        return None
    facts = evidence["facts"]
    if len(facts) != 1 or evidence["lifecycle_status"] != "active":
        return "stale"
    if facts[0]["detector_status"] != "active" or not valid_link(db, evidence, facts[0]):
        return "stale"
    result = state(db, evidence["position_id"], evidence["subject"], _history=_history)
    return {"current": "current", "needed": "stale"}.get(result, "unavailable")
