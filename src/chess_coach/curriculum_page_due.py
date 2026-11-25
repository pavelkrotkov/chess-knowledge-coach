"""Collect due work before any new curriculum material."""

from .curriculum_due_scan import scan_due


def due(db, state, now, summary, scan, window=None):
    if state["phase"] != "due":
        return [], None
    items, scan["due_examined"], scan["due_incomplete"], reason = scan_due(
        db, state, now, summary, scan, window
    )
    if reason is None and scan["due_incomplete"] and len(state["seen"]) < state["limit"]:
        reason = "due_scan_incomplete"
    return items, reason
