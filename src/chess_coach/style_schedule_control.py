"""Choose a verified early-center control or retain ordinary rotation."""

from .style_schedule_independent import controls
from .style_schedule_priority import choose as choose_priority
from .style_schedule_rotation import choose


def select(db, key, sequence, candidates, target):
    ordinary = controls(candidates, target, False)
    targetable = None
    if sequence % 4 == 1:
        if target:
            targetable = controls(candidates, target, True)
        else:
            targetable = [item for item in ordinary if item.get("_game_key")]
    return control(db, key, sequence, ordinary, targetable=targetable)


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
