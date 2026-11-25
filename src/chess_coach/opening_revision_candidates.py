"""Qualify each alternative with the existing all-root admission gate."""

from .opening_experiment import MAX_DISADVANTAGE, assess


def admission(decision, choice, states):
    state = states.get(choice["uci"], {})
    if state.get("status") != "complete":
        return {"status": "unknown", "reason": state.get("status", "unavailable")}
    if state.get("policy") != "all-legal-roots-v2":
        return {"status": "unknown", "reason": "all_root_reference_unavailable"}
    experiment, reason = assess(decision, choice, state)
    if experiment is None:
        status = "rejected" if reason in {"score_gap", "reference_gap"} else "unknown"
        return {"status": status, "reason": reason}
    lines = {line["root_move"]: line for line in state["lines"]}
    played = lines[decision["played_uci"]]["score_value"]
    return {
        "status": "eligible",
        "played_admitted": played >= experiment["reference"]["score"] - MAX_DISADVANTAGE,
        "policy": state["policy"],
        "depth": experiment["depth"],
        "reference": experiment["reference"],
    }


def initial(decision, states):
    return [
        {"choice": item, "admission": admission(decision, item, states)}
        for item in decision["catalog"]["items"]
    ]
