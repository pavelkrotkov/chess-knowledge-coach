"""Track non-check control coverage separately from check and protection choices."""

from .style_center_control import observation


def overlap(kind, snapshot, state):
    if kind == "control" and snapshot is not None and not snapshot["board"].is_check():
        state["center_control"]["coverage"]["overlap"] += 1


def collect(db, context, slot, snapshot, view, state, key, result):
    if slot["kind"] != "control" or result != "outside_check":
        return
    target = state["center_control"]
    if key in target["seen"]:
        target["coverage"]["duplicate"] += 1
        return
    target["seen"].add(key)
    target["coverage"]["examined"] += 1
    try:
        status, item = observation(db, context, slot, snapshot, view)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        status, item = "unavailable", None
    target["coverage"][status] += 1
    if item is not None:
        target["observations"].append(item)
