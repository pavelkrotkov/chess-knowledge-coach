"""Apply tactical exposure only to held-out assessment decisions."""

from .related_capture_position import prompt_key
from .tactical_exposure_check import check


def eligible(db, subject, item):
    key = item.get("prompt_key")
    return isinstance(key, str) and check(db, subject, key) == "not_recorded"


def require_assessment(db, subject, row, binding):
    if not isinstance(binding.get("assessment"), dict):
        return
    reason = check(db, subject, prompt_key(row["prompt_fen"]))
    if reason != "not_recorded":
        raise ValueError("held-out assessment unavailable: " + reason)


def filter_eligible(db, subject, items, limit):
    return [item for item in items[:limit] if eligible(db, subject, item)]
