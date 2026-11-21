"""Canonical supported choices for an explicitly selected tactical course."""

from .tactical_course_selection import CURRENT_PAIRS

MAX_CHOICES = 3
WORK_POLICY = "selected-tactical-work-v1"
SLICE_SECONDS = 8.0


def normalize(values):
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_CHOICES:
        raise ValueError("choose one to three tactical weaknesses")
    allowed = [f"{skill}:{operation}" for skill, operation in CURRENT_PAIRS]
    try:
        chosen = set(values)
        if len(chosen) != len(values) or not chosen.issubset(allowed):
            raise ValueError("unsupported or duplicate tactical weakness")
    except TypeError:
        raise ValueError("unsupported tactical weakness") from None
    return sorted(chosen, key=allowed.index)


def pairs(values):
    return [tuple(value.split(":")) for value in normalize(values)]


def from_pairs(value):
    try:
        if not isinstance(value, list):
            raise ValueError("invalid tactical weakness selection")
        chosen = pairs([":".join(pair) for pair in value])
        if [list(pair) for pair in chosen] != value:
            raise ValueError("tactical weakness order changed")
        return chosen
    except TypeError:
        raise ValueError("invalid tactical weakness selection") from None


def check_budget(selected, budget):
    if selected and budget.slice_seconds != SLICE_SECONDS:
        raise ValueError("selected course work policy differs")
