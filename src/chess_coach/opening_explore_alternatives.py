"""Describe current same-exemplar comparisons without broadening their evidence."""

from .opening_experiment import assess

STATES = {"none", "queued", "unavailable", "stale"}


def _complete(exemplar, choice, state):
    lines = {line["root_move"]: line for line in state["lines"]}
    played, alternative = lines.get(exemplar["played_uci"]), lines.get(choice["uci"])
    if played is None or alternative is None:
        return {"status": "unknown"}
    experiment, reason = assess(exemplar, choice, state)
    return {
        "status": "complete",
        "played": played["score_value"],
        "alternative": alternative["score_value"],
        "depth": played["depth"],
        "ready": experiment is not None,
        "reason": reason,
    }


def describe(exemplar, states):
    output = []
    for choice in exemplar["catalog"]["items"]:
        state = states.get(choice["uci"], {})
        status = state.get("status")
        summary = (
            _complete(exemplar, choice, state)
            if status == "complete"
            else {"status": status if status in STATES else "unknown"}
        )
        output.append({"choice": choice, **summary})
    return output
