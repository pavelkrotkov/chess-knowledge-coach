"""Summarize and explain bounded qualified-family priority."""

from .curriculum_priority_decision import THRESHOLD, winner
from .curriculum_priority_evidence import family
from .mastery_time import parse_utc

SKILLS = {"capture": "hanging_piece", "fork": "fork"}


def unknown():
    value = {"state": "incomplete", "contexts": None, "mastery": None, "uncertainty": None}
    return {"winner": "rotate", "capture": dict(value), "fork": dict(value)}


def snapshot(db, learner, state, check):
    now = parse_utc(state["as_of"])
    if now is None:
        raise ValueError("qualified priority time unavailable")
    values = {
        name: family(db, learner, skill, now, state["scan_limit"], check)
        for name, skill in SKILLS.items()
    }
    return {"winner": winner(values["capture"], values["fork"]), **values}


def explain(state, family):
    values = state["priority"][family]
    if values["state"] != "sufficient":
        return "Family-level weakness is unknown; the task source review is stated separately."
    if values["mastery"] < THRESHOLD:
        description = "A current reviewed weakness is supported"
    else:
        description = "No current reviewed weakness is supported"
    details = (
        f" by {values['contexts']} independent contexts (uncertainty {values['uncertainty']:.2f})."
    )
    if state["priority"]["winner"] == family and state["priority_goal"] not in {"capture", "fork"}:
        return description + details + " This family is ordered earlier among owned choices."
    return description + details
