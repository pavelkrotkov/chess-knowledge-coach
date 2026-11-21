"""Choose one bounded new item per family before filling from the mate corpus."""

import time
from contextlib import nullcontext

from .curriculum_cursor_families import current_family
from .curriculum_new_capture import scan as capture
from .curriculum_new_fork import scan as fork
from .curriculum_new_page import checked_page
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable


def _advance(state):
    state["family_index"] += 1
    state["phase"] = current_family(state)


def _step(db, state, learner, summary, counts, corpus, budget, check):
    phase = state["phase"]
    if phase == "capture":
        items, status, reason, focus = capture(
            db, state, learner, counts, budget, shared_check=check
        )
        return items, status, reason, focus
    if phase == "fork":
        return fork(db, state, learner, counts, check)
    return checked_page(db, state, summary, counts, corpus, check)


def _defer(state):
    phase = state["phase"]
    pending = {"capture": "capture_pending", "fork": "fork_pending", "new": "pending"}
    if state["family_index"] < 3 and state[pending[phase]] is None:
        _advance(state)
        return "family_scan_incomplete"
    return f"{phase}_scan_incomplete"


def scan(db, state, learner, summary, counts, corpus, budget):
    expires = time.monotonic() + SLICE_SECONDS

    def check():
        if time.monotonic() >= expires:
            raise PreviewUnavailable("request deadline reached")

    # A single scope and clock cover every family on this response page.
    progress = {"items": [], "statuses": {}, "focuses": {}, "reason": None, "checkpoint": None}
    scope = budget.scope(snapshot=False) if budget is not None else nullcontext()
    try:
        with scope:
            _loop(db, state, learner, summary, counts, corpus, budget, check, progress)
    except PreviewUnavailable:
        _timeout(db, state, counts, budget, progress)
    return progress["items"], progress["statuses"], progress["focuses"], progress["reason"]


def _loop(db, state, learner, summary, counts, corpus, budget, check, progress):
    while len(state["seen"]) < state["limit"]:
        phase = state["phase"]
        # Only a completed family can be published after a timeout.
        progress["checkpoint"] = (dict(state), dict(counts), len(progress["items"]))
        found, status, reason, focus = _step(
            db,
            state,
            learner,
            summary,
            counts,
            corpus,
            budget,
            check if budget is not None else None,
        )
        _check_completed(reason, budget, check)
        progress["items"].extend(found)
        progress["statuses"][phase] = status
        progress["focuses"][phase] = focus
        if _fill_quota(state, reason):
            progress["reason"] = None
            continue
        if reason == "family_quota_complete":
            reason = None
        reason = _reason(state, reason)
        progress["reason"] = reason
        if reason is not None or state["family_index"] == 3:
            break
        _advance(state)


# Each successful item in final fill is its own durable cursor checkpoint.
def _fill_quota(state, reason):
    return reason == "family_quota_complete" and state["family_index"] == 3


# Do not publish a just-completed item after its shared deadline.
def _check_completed(reason, budget, check):
    if budget is not None and reason in {None, "family_quota_complete"}:
        check()


def _reason(state, reason):
    if reason in {"capture_scan_incomplete", "fork_scan_incomplete"}:
        return _defer(state)
    # Yield to other families only during the one-item corpus pass.
    if reason == "corpus_scan_incomplete" and state["family_index"] < 3:
        return _defer(state)
    return reason


def _timeout(db, state, counts, budget, progress):
    # A changed database invalidates completed families as well as the pending one.
    if (
        budget is not None
        and db.connection.execute("PRAGMA data_version").fetchone()[0] != budget.version
    ):
        raise ValueError("curriculum sources changed; restart the plan") from None
    if progress["reason"] is not None:
        return
    phase = state["phase"]
    pending_key = {"capture": "capture_pending", "fork": "fork_pending", "new": "pending"}[phase]
    pending = state[pending_key]
    after = state["scheduled_after"]
    # The prior corpus coordinate and its pending candidate are one continuation.
    new_after = state["new_after"]
    # Rewind only the unfinished family; earlier checked items can still be shown.
    checkpoint = progress["checkpoint"]
    if checkpoint is not None:
        saved_state, saved_counts, size = checkpoint
        state.update(saved_state)
        counts.update(saved_counts)
        del progress["items"][size:]
    # A bound candidate must resume its conflict check before another family.
    if pending is not None and state["phase"] == phase:
        state[pending_key], state["scheduled_after"] = pending, after
        if phase == "new":
            state["new_after"] = new_after
    phase = state["phase"]
    progress["statuses"][phase] = "deferred"
    progress["reason"] = _defer(state)
