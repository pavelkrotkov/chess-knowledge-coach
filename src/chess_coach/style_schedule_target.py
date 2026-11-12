"""Choose a fully replayed target while preserving fallback rotation."""

from .style_schedule_priority import choose as choose_structural
from .style_schedule_priority import independent
from .style_schedule_rotation import choose


def _structural(item):
    return item["status"] == "ready" and item["structural_defense"] is True


def _unknown(item):
    return item["status"] == "ready" and item["structural_defense"] is None


def target(db, key, sequence, candidates):
    targets = [item for item in candidates if item["in_check"]]
    structural = [item for item in targets if _structural(item)]
    unknown = sum(_unknown(item) for item in targets)
    if sequence % 4 == 1:
        targets = independent(targets, candidates)
    selected = _choose(db, key, sequence, targets, structural)
    return selected, len(structural), unknown


def _choose(db, key, sequence, targets, structural):
    if sequence % 2 == 0 and structural:
        return choose_structural(key, sequence, structural)
    return choose(db, key, "target", targets)
