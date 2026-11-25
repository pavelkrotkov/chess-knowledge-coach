"""Explain whether the chosen goal produced an eligible new item."""

SKILLS = {
    "capture": "hanging_piece",
    "fork": "fork",
    "mate": "mate_in_one",
    "promotion": "promotion",
}
FIELDS = {
    "capture": "capture_status",
    "fork": "fork_status",
    "mate": "public_status",
    "promotion": "canonical_status",
}


def status(page, goal):
    if goal == "balanced":
        return "balanced"
    if any(item["kind"] == "new" and item["skill"] == SKILLS[goal] for item in page["items"]):
        return "available"
    if page["scan"]["due_incomplete"] or page.get("limit_reached"):
        return "not_checked"
    value = page.get(FIELDS[goal])
    if _unknown(page, goal, value):
        return "unknown"
    return "unavailable"


def annotate(page, goal):
    if goal == "balanced":
        return
    for item in page["items"]:
        if item["kind"] == "new" and item["skill"] == SKILLS[goal]:
            item["reason"] = "Requested goal: " + item["reason"]


def _unknown(page, goal, value):
    if value in {None, "unchecked", "deferred", "not_scanned"}:
        return True
    return goal == "mate" and page.get("corpus_status") in {
        "not_scanned",
        "scan_incomplete",
        "scheduled_scan_incomplete",
    }
