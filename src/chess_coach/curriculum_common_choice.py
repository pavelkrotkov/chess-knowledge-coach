"""Stage actual owned candidates against one resumable schedule frontier."""

from .curriculum_common_candidates import collect
from .curriculum_common_ranking import rank


def stage(db, state, subject, scan, root, check, bundle):
    selected = collect(db, state, scan, check, bundle)
    if selected is None:
        return None
    options, fork, fork_focus, matched, incomplete, reason, advisory = selected
    if incomplete is not None:
        return [], incomplete, reason, advisory, state["phase"]
    capture, focus, blocked, rationale, winner, explanation = rank(
        db, state, subject, root, options, fork, matched, check, bundle
    )
    pending = "capture_pending" if state["phase"] == "capture" else "fork_pending"
    state[pending] = None
    return _publish(
        state, capture, focus, fork, fork_focus, blocked, rationale, winner, explanation
    )


def _publish(state, capture, focus, fork, fork_focus, blocked, rationale, winner, explanation):
    phase = winner or state["phase"]
    candidate, selected_focus = (capture, focus) if phase == "capture" else (fork, fork_focus)
    selected_focus = dict(selected_focus)
    selected_focus.pop("snapshot", None)
    if candidate["prompt_key"] in blocked:
        state["phase"] = "new"
        return [], "already_scheduled", None, selected_focus, phase
    if phase == "capture":
        candidate["reason"] += " " + rationale
    if winner:
        candidate["reason"] += " " + explanation
    state["seen"] = sorted([*state["seen"], candidate["prompt_key"]])
    state["phase"] = "new"
    item = {key: value for key, value in candidate.items() if key != "binding"}
    return [item], "offered", None, selected_focus, phase
