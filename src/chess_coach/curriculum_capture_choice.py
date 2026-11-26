"""Choose between two current owned capture witnesses with comparable practice."""

from .curriculum_capture_conflicts import scheduled
from .curriculum_capture_rank import choice
from .curriculum_capture_source import practice_reason
from .curriculum_capture_witnesses import candidates, pending


def select(db, state, subject, scan, check):
    options, status, identity = candidates(db, subject, state["corpus_version"], check)
    state["priority"]["capture_sources"] = identity
    if not options:
        if state["capture_pending"] is not None:
            raise ValueError("capture source changed")
        state["phase"] = "new"
        return [], status, None, None
    binding = pending(identity, options)
    if state["capture_pending"] not in {None, binding}:
        raise ValueError("capture source changed")
    state["capture_pending"] = binding
    matched, incomplete, reason = scheduled(db, state, scan, options, check)
    if incomplete is not None:
        return [], incomplete, reason, options[0][1]
    state["capture_pending"] = None
    state["scheduled_after"] = 0
    state["priority"]["capture_matches"] = 0
    chosen, qualified = choice(db, subject, state, options, matched, check)
    candidate, report = options[chosen]
    if candidate["prompt_key"] in matched | set(state["seen"]):
        state["phase"] = "new"
        return [], "already_scheduled", None, report
    candidate["reason"] += " " + practice_reason(qualified)
    state["seen"] = sorted([*state["seen"], candidate["prompt_key"]])
    state["phase"] = "new"
    return (
        [{key: value for key, value in candidate.items() if key != "binding"}],
        "offered",
        None,
        report,
    )
