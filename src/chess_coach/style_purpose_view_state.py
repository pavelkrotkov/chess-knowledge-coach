"""Classify exact purpose attempts for report eligibility."""


def view_state(view):
    if view["source_state"] != "current":
        return "stale"
    if view["status"] != "complete":
        return view["status"]
    if not view["attempts"]:
        return "insufficient"
    attempt = view["attempts"][-1]
    if attempt["status"] != "complete" or not attempt.get("final"):
        return "insufficient"
    if attempt["final"]["comparison_issue"] is not None:
        return "insufficient"
    return "current"


def unavailable(slot):
    return {
        "request_id": slot["request_id"],
        "game_id": slot["game_id"],
        "position_id": slot["position_id"],
        "source_state": "unavailable",
        "status": "unknown",
        "attempts": [],
    }
