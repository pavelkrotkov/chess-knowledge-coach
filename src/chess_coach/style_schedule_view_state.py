"""Resolve a scheduled request status without exposing stale lines."""


def view_state(view):
    if view["source_state"] == "stale":
        return "stale"
    if view["status"] == "complete":
        return view["attempts"][-1]["status"] if view["attempts"] else "insufficient"
    return view["status"]
