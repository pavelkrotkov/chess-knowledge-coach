"""Check the immutable observation and its current source without replaying scans."""

from .king_safety_mapping import MAPPER
from .king_safety_probe import state
from .material_opportunity_links import valid_link


def currentness(db, evidence, *, _history=None):
    if evidence["mapping_producer"] != MAPPER:
        return None
    facts = evidence["facts"]
    if (
        len(facts) != 1
        or evidence["lifecycle_status"] != "active"
        or facts[0]["detector_status"] != "active"
        or not valid_link(db, evidence, facts[0])
    ):
        return "stale"
    return (
        "current"
        if state(db, evidence["position_id"], evidence["subject"], _history=_history) == "current"
        else "stale"
    )
