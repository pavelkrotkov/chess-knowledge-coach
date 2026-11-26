"""Choose between two current owned capture witnesses with comparable practice."""

from .curriculum_capture_conflicts import scheduled
from .curriculum_capture_rank import choice
from .curriculum_capture_witnesses import candidates, pending


def select(db, state, subject, scan, check, *, root=None):
    from .curriculum_priority_cursor import CONTEXT_CAPTURE_POLICY

    options, status, identity, advisory = candidates(
        db,
        subject,
        state["corpus_version"],
        check,
        include_snapshot=state["priority_policy"] == CONTEXT_CAPTURE_POLICY,
    )
    state["priority"]["capture_sources"] = identity
    if not options:
        if state["capture_pending"] is not None:
            raise ValueError("capture source changed")
        state["phase"] = "new"
        return [], status, None, advisory
    binding = pending(identity, options)
    if state["capture_pending"] not in {None, binding}:
        raise ValueError("capture source changed")
    state["capture_pending"] = binding
    matched, incomplete, reason = scheduled(db, state, scan, options, check)
    if incomplete is not None:
        report = options[0][1]
        report.pop("snapshot", None)
        return [], incomplete, reason, report
    state["capture_pending"] = None
    state["scheduled_after"] = 0
    state["priority"]["capture_matches"] = 0
    chosen, rationale = choice(db, subject, state, options, matched, check, root=root)
    candidate, report = options[chosen]
    report.pop("snapshot", None)
    if candidate["prompt_key"] in matched | set(state["seen"]):
        state["phase"] = "new"
        return [], "already_scheduled", None, report
    candidate["reason"] += " " + rationale
    state["seen"] = sorted([*state["seen"], candidate["prompt_key"]])
    state["phase"] = "new"
    return (
        [{key: value for key, value in candidate.items() if key != "binding"}],
        "offered",
        None,
        report,
    )
