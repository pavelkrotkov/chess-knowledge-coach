"""Preserve completed work and bound candidates across a plan deadline."""

from .curriculum_mix_order import advance as _advance
from .curriculum_mix_order import recovery


def defer(state):
    phase = state["phase"]
    pending = {
        "capture": "capture_pending",
        "fork": "fork_pending",
        "new": "pending",
        "public": "public_pending",
        "canonical": "canonical_pending",
    }
    # An unbound deadline remains deferred work, not proof of an absent source.
    if phase in {"public", "canonical"}:
        state[phase + "_status"] = "deferred"
    elif state["v"] in {6, 8} and phase in {"capture", "fork"}:
        state[phase + "_mix"] = "deferred"
    end = 8 if state["v"] in {6, 8} else 3
    if state["family_index"] < end and state[pending[phase]] is None:
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
    checkpoint = progress["checkpoint"]
    saved, _, size = checkpoint or (state, counts, 0)
    phase, completed = recovery(state, saved, progress, size)
    pending_key = {
        "capture": "capture_pending",
        "fork": "fork_pending",
        "new": "pending",
        "public": "public_pending",
        "canonical": "canonical_pending",
    }[phase]
    pending = state[pending_key]
    after = state["scheduled_after"]
    # The prior corpus coordinate and its pending candidate are one continuation.
    new_after = state["new_after"]
    source = _source_position(state, phase)
    pending, after, source = _source_rewind(state, saved, counts, phase, pending, after, source)
    # Rewind only the unfinished family; earlier checked items can still be shown.
    if checkpoint is not None:
        saved_state, saved_counts, size = checkpoint
        state.update(saved_state)
        counts.update(saved_counts)
        del progress["items"][size:]
    _restore(state, phase, pending_key, pending, after, new_after, source)
    phase = state["phase"]
    progress["statuses"][phase] = "deferred"
    progress["reason"] = _retry_or_defer(state, phase, completed)


def _retry_or_defer(state, phase, completed):
    if completed and state["v"] in {5, 6, 8} and phase in {"capture", "fork"}:
        return f"{phase}_scan_incomplete"
    return defer(state)


def _source_position(state, phase):
    return state.get(phase + "_after"), state.get(phase + "_examined")


def _restore(state, phase, key, pending, after, new_after, source):
    if state["phase"] != phase:
        return
    if phase in {"public", "canonical"}:
        state[phase + "_after"], state[phase + "_examined"] = source
    if pending is not None:
        state[key], state["scheduled_after"] = pending, after
        if phase == "new":
            state["new_after"] = new_after


def _source_rewind(state, saved, counts, phase, pending, after, source):
    if phase not in {"public", "canonical"}:
        return pending, after, source
    if not state.get(phase + "_binding") or saved.get(phase + "_binding"):
        return pending, after, source
    if saved[phase + "_pending"] is not None:
        return saved[phase + "_pending"], saved["scheduled_after"], _source_position(saved, phase)
    prior = counts.get("_" + phase + "_before", _source_position(saved, phase))
    return None, 0, prior
