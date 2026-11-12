"""Choose a verified early-center control or retain ordinary rotation."""

from .style_schedule_fresh import available
from .style_schedule_independent import controls
from .style_schedule_priority import choose as choose_priority
from .style_schedule_rotation import choose


def _targetable(candidates, ordinary, target):
    if target:
        return controls(candidates, target, True)
    return [item for item in ordinary if item.get("_game_key")]


def select(db, key, sequence, candidates, target, *, identities=None):
    ordinary = controls(candidates, target, False)
    targetable = None
    nominated = sum(bool(item.get("early_center")) for item in ordinary)
    if sequence % 4 == 1:
        targetable = _targetable(candidates, ordinary, target)
        early = [item for item in targetable if item.get("early_center")]
        nominated = len(early)
        targetable = available(db, key, early, identities or {})
    selected, targeted, _ = control(db, key, sequence, ordinary, targetable=targetable)
    return selected, targeted, nominated


def control(db, key, sequence, ordinary, *, targetable=None):
    source = ordinary if targetable is None else targetable
    early = [item for item in source if item.get("early_center")]
    targeted = sequence % 4 == 1 and bool(early)
    selected = (
        choose_priority(key, sequence // 2, early)
        if targeted
        else choose(db, key, "control", ordinary)
    )
    return selected, targeted, len(early)
