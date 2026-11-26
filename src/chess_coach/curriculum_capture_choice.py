"""Choose between two current owned capture witnesses with comparable practice."""

from .curriculum_capture_conflicts import scheduled
from .curriculum_capture_rank import choice
from .curriculum_capture_witnesses import candidates


def select(db, state, subject, scan, check):
    options, status, identity = candidates(db, subject, state["corpus_version"], check)
    state["priority"]["capture_sources"] = identity
    if not options:
        state["phase"] = "new"
        return [], status, None, None
    matched = scheduled(db, state, scan, check)
    if matched is None:
        return [], "unavailable", "scheduled_prompt_unavailable", options[0][1]
    chosen, qualified = choice(db, subject, state, options, matched, check)
    candidate, report = options[chosen]
    if candidate["prompt_key"] in matched or candidate["prompt_key"] in state["seen"]:
        state["phase"] = "new"
        return [], "already_scheduled", None, report
    note = "Dated capture opportunity importance is unknown."
    if qualified:
        note += " Comparable verified practice selected the previously unmet capture."
    else:
        note += " Comparable practice priority is unknown or tied; source order is retained."
    candidate["reason"] += " " + note
    state["seen"] = sorted([*state["seen"], candidate["prompt_key"]])
    state["phase"] = "new"
    return (
        [{key: value for key, value in candidate.items() if key != "binding"}],
        "offered",
        None,
        report,
    )
