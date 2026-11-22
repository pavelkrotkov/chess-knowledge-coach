"""Choose one bounded new item per family before filling from the mate corpus."""

import time
from contextlib import nullcontext

from .curriculum_cursor_families import current_family
from .curriculum_family_checkpoint import defer, timeout
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
    if phase == "public":
        from .curriculum_public_scan import scan

        return scan(db, state, learner, counts, check)
    return checked_page(db, state, summary, counts, corpus, check)


def scan(db, state, learner, summary, counts, corpus, budget):
    expires = time.monotonic() + SLICE_SECONDS

    def check():
        if time.monotonic() >= expires:
            raise PreviewUnavailable("request deadline reached")

    # A single scope and clock cover the topic and every family on this page.
    progress = {"items": [], "statuses": {}, "focuses": {}, "reason": None, "checkpoint": None}
    scope = budget.scope(snapshot=False) if budget is not None else nullcontext()
    try:
        with scope:
            # Topic preparation precedes selection, but never changes grading.
            if state["v"] in {4, 5}:
                from .curriculum_prerequisite import prepare

                progress["statuses"]["prerequisite"] = prepare(
                    db, state, learner, summary, check if budget is not None else None
                )
            _loop(db, state, learner, summary, counts, corpus, budget, check, progress)
    except PreviewUnavailable:
        timeout(db, state, counts, budget, progress)
    counts.pop("_public_before", None)
    return progress["items"], progress["statuses"], progress["focuses"], progress["reason"]


def _loop(db, state, learner, summary, counts, corpus, budget, check, progress):
    while len(state["seen"]) < state["limit"]:
        phase = state["phase"]
        if _skip(state, phase):
            break
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
        from .curriculum_prerequisite import offer_items

        # Bind the optional diagnostic only after candidate selection succeeds.
        found = offer_items(
            db, state, learner, found, phase, progress["statuses"].get("prerequisite"), check
        )
        progress["items"].extend(found)
        progress["statuses"][phase] = status
        progress["focuses"][phase] = focus
        if _fill_quota(state, reason, found):
            progress["reason"] = None
            continue
        if reason == "family_quota_complete":
            reason = None
        reason = _reason(state, reason)
        progress["reason"] = reason
        if reason is not None or _finished(state, phase):
            break
        _advance(state)


# Each successful item in final fill is its own durable cursor checkpoint.
def _fill_quota(state, reason, found):
    if reason != "family_quota_complete":
        return False
    return not found if state["v"] == 5 else state["family_index"] == 3


def _skip(state, phase):
    return state["v"] == 5 and phase == "new" and state["public_binding"] is not None


def _finished(state, phase):
    return (state["v"] == 5 and phase == "new") or (state["v"] != 5 and state["family_index"] == 3)


# Do not publish a just-completed item after its shared deadline.
def _check_completed(reason, budget, check):
    if budget is not None and reason in {None, "family_quota_complete"}:
        check()


def _reason(state, reason):
    if reason in {"capture_scan_incomplete", "fork_scan_incomplete", "public_scan_incomplete"}:
        return defer(state)
    # Yield to other families only during the one-item corpus pass.
    if reason == "corpus_scan_incomplete" and state["family_index"] < 3:
        return defer(state)
    return reason
