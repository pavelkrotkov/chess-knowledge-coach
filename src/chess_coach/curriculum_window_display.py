"""Explain whether the chosen goal produced an eligible new item."""

from .curriculum_window_match import matches

FIELDS = {
    "capture": "capture_status",
    "fork": "fork_status",
    "mate": "public_status",
    "promotion": "canonical_status",
}


def status(page, goal):
    if goal == "balanced":
        return "balanced"
    if any(matches(item, goal) for item in page["items"]):
        return "available"
    if page["scan"]["due_incomplete"] or page.get("limit_reached"):
        return "not_checked"
    value = page.get(FIELDS[goal])
    if _unknown(value):
        return "unknown"
    return "unavailable"


def annotate(page, goal):
    if goal == "balanced":
        return
    for item in page["items"]:
        if matches(item, goal):
            item["reason"] = "Requested goal: " + item["reason"]


def _unknown(value):
    return value in {None, "unchecked", "deferred", "not_scanned", "exposure_unknown", "incomplete"}
