"""Preserve the current family when preparation or proof is interrupted."""


def retry_or_defer(state, phase, completed, defer):
    if state["v"] == 8 and state["priority"] is None:
        return "priority_scan_incomplete"
    if completed and state["v"] in {5, 6, 8} and phase in {"capture", "fork"}:
        return f"{phase}_scan_incomplete"
    return defer(state)


def restore(state, phase, key, pending, after, new_after, source, common):
    if state["phase"] != phase:
        return
    if common is not None:
        state["common"] = common
    if phase in {"public", "canonical"}:
        state[phase + "_after"], state[phase + "_examined"] = source
    if pending is not None:
        state[key], state["scheduled_after"] = pending, after
        if phase == "new":
            state["new_after"] = new_after
