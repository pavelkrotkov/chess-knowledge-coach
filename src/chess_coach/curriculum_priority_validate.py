"""Validate signed qualified-family evidence summaries."""

from .curriculum_cursor_values import hex_digest
from .curriculum_priority_value import bounds


def validate_priority(value, limit, *, capture=False):
    if value is None:
        return
    fields = {"winner", "capture", "fork"} | (
        {"capture_input", "capture_sources"} if capture else set()
    )
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("invalid qualified priority")
    if capture:
        _capture(value)
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


def _capture_input(value):
    if not hex_digest(value):
        raise ValueError("invalid capture practice input")


def _capture(value):
    _capture_input(value["capture_input"])
    if value["capture_sources"] is not None:
        _capture_input(value["capture_sources"])
