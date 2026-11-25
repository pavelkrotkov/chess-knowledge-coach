"""Preserve the current family when preparation or proof is interrupted."""


def retry_or_defer(state, phase, completed, defer):
    if state["v"] == 8 and state["priority"] is None:
        return "priority_scan_incomplete"
    if completed and state["v"] in {5, 6, 8} and phase in {"capture", "fork"}:
        return f"{phase}_scan_incomplete"
    return defer(state)
