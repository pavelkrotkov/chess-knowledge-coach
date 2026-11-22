"""Preserve completed work and bound candidates across a plan deadline."""

from .curriculum_cursor_families import current_family


def _advance(state):
    state["family_index"] += 1
    state["phase"] = current_family(state)


def defer(state):
    phase = state["phase"]
    pending = {
        "capture": "capture_pending",
        "fork": "fork_pending",
        "new": "pending",
        "public": "public_pending",
    }
    if phase == "public":
        state["public_status"] = "deferred"
    if state["family_index"] < 3 and state[pending[phase]] is None:
        _advance(state)
        return "family_scan_incomplete"
    return f"{phase}_scan_incomplete"


def timeout(db, state, counts, budget, progress):
    # A changed database invalidates completed families as well as the pending one.
    if (
        budget is not None
        and db.connection.execute("PRAGMA data_version").fetchone()[0] != budget.version
    ):
        raise ValueError("curriculum sources changed; restart the plan") from None
    if progress["reason"] is not None:
        return
    phase = state["phase"]
    pending_key = {
        "capture": "capture_pending",
        "fork": "fork_pending",
        "new": "pending",
        "public": "public_pending",
    }[phase]
    pending = state[pending_key]
    after = state["scheduled_after"]
    # The prior corpus coordinate and its pending candidate are one continuation.
    new_after = state["new_after"]
    public_after = state.get("public_after")
    public_examined = state.get("public_examined")
    # Rewind only the unfinished family; earlier checked items can still be shown.
    checkpoint = progress["checkpoint"]
    if checkpoint is not None:
        saved_state, saved_counts, size = checkpoint
        state.update(saved_state)
        counts.update(saved_counts)
        del progress["items"][size:]
    _restore(state, phase, pending_key, pending, after, new_after, public_after, public_examined)
    phase = state["phase"]
    progress["statuses"][phase] = "deferred"
    progress["reason"] = defer(state)


def _restore(state, phase, key, pending, after, new_after, public_after, public_examined):
    if state["phase"] != phase:
        return
    if phase == "public":
        state["public_after"], state["public_examined"] = public_after, public_examined
    if pending is not None:
        state[key], state["scheduled_after"] = pending, after
        if phase == "new":
            state["new_after"] = new_after
