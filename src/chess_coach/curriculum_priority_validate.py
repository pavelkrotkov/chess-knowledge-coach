"""Validate signed qualified-family evidence summaries."""

from .curriculum_priority_value import bounds


def validate_priority(value, limit):
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"winner", "capture", "fork"}:
        raise ValueError("invalid qualified priority")
    if value["winner"] not in {"capture", "fork", "rotate"}:
        raise ValueError("invalid qualified priority")
    for family in ("capture", "fork"):
        _family(value[family], limit)


def _family(value, limit):
    if not isinstance(value, dict) or set(value) != {"state", "contexts", "mastery", "uncertainty"}:
        raise ValueError("invalid qualified evidence")
    if value["state"] not in {"sufficient", "insufficient", "incomplete"}:
        raise ValueError("invalid qualified evidence")
    bounds(value, limit)
