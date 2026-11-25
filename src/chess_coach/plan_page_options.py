"""Validate plan form values and choose the optional promotion priority."""

from .next_focus_select import repeats_success
from .plan_page_focus import generation as current_generation


def minutes(value):
    if value in (None, ""):
        return None
    if not value.isascii() or not value.isdigit():
        raise ValueError("invalid practice window")
    return int(value)


def priority(db, promotion, focus, generation):
    return bool(
        promotion
        and promotion["status"] == "ready"
        and repeats_success(focus)
        and generation is not None
        and current_generation(db) == generation
    )
