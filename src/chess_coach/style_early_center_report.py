"""Count only current targeted comparisons of actual first roots."""

from collections import Counter

from .style_early_center_compare import observation


def note(state, slot, reason):
    if slot.get("early_center_target"):
        state["early_center"]["coverage"][reason] += 1


def collect(context, slot, snapshot, view, state):
    if not slot.get("early_center_target"):
        return
    target = state["early_center"]
    key = (slot["game_id"], slot["position_id"])
    if key in target["seen"]:
        target["coverage"]["duplicate"] += 1
        return
    # Multiple scheduled slots can point to one decision; count it once.
    target["seen"].add(key)
    try:
        status, result = observation(context, slot, snapshot, view)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        status, result = "unsupported", None
    target["coverage"][status] += 1
    if result is not None:
        target["observations"].append(result)


def summary(state):
    items = state["observations"]
    names = (
        "cycles",
        "fallback",
        "slots",
        "admitted",
        "no_contrast",
        "unsupported",
        "stale",
        "unchecked",
        "ordinary_overlap",
        "duplicate",
    )
    return {
        "coverage": {name: state["coverage"].get(name, 0) for name in names},
        "choices": dict(Counter(item["choice"] for item in items)),
        "games": len({item["game_id"] for item in items}),
        "observations": items,
    }


def slot_coverage(row, contexts, coverage):
    if not row.get("early_center_cycle"):
        return
    coverage["cycles"] += 1
    if not row.get("early_center_target"):
        coverage["fallback"] += 1
        coverage["unchecked"] += 1
        return
    coverage["slots"] += 1
    if (
        row["game_id"] not in contexts
        or row["position_id"] not in contexts[row["game_id"]]
        or row["request_id"] is None
    ):
        coverage["unchecked"] += 1
