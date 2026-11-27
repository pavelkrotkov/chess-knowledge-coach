"""Choose one bounded new item per family before filling from the mate corpus."""

import time
from contextlib import nullcontext

from .curriculum_family_checkpoint import reason as classify_reason
from .curriculum_family_checkpoint import timeout
from .curriculum_mix_order import action, mark, record
from .curriculum_mix_order import advance as _advance
from .curriculum_new_capture import scan as capture
from .curriculum_new_fork import scan as fork
from .curriculum_new_page import checked_page
from .curriculum_priority_prepare import annotate, prepare_priority
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable


def _step(db, state, learner, summary, counts, corpus, budget, check):
    phase = state["phase"]
    staged = _common(db, state, learner, counts, budget, check)
    if staged is not None:
        return staged
    if phase == "capture":
        result = capture(db, state, learner, counts, budget, shared_check=check)
    elif phase == "fork":
        result = fork(db, state, learner, counts, check)
    elif phase == "public":
        from .curriculum_public_scan import scan

        result = scan(db, state, learner, counts, check)
    elif phase == "canonical":
        from .curriculum_canonical_scan import scan

        result = scan(db, state, learner, counts, check)
    else:
        result = checked_page(db, state, summary, counts, corpus, check)
    return (*result, phase)


def scan(db, state, learner, summary, counts, corpus, budget):
    expires = time.monotonic() + SLICE_SECONDS

    def check():
        if time.monotonic() >= expires:
            raise PreviewUnavailable("request deadline reached")
        if budget is not None:
            budget.check()

    # A single scope and clock cover the topic and every family on this page.
    progress = {"items": [], "statuses": {}, "focuses": {}, "reason": None, "checkpoint": None}
    scope = budget.scope(snapshot=False) if budget is not None else nullcontext()
    try:
        with scope:
            # Topic preparation precedes selection, but never changes grading.
            if state["v"] in {4, 5, 6, 8}:
                from .curriculum_prerequisite import prepare

                progress["statuses"]["prerequisite"] = prepare(
                    db, state, learner, summary, check if budget is not None else None
                )
            prepare_priority(db, state, learner, budget, check)
            _loop(db, state, learner, summary, counts, corpus, budget, check, progress)
    except PreviewUnavailable:
        timeout(db, state, counts, budget, progress)
    counts.pop("_public_before", None)
    counts.pop("_canonical_before", None)
    return progress["items"], progress["statuses"], progress["focuses"], progress["reason"]


def _loop(db, state, learner, summary, counts, corpus, budget, check, progress):
    while len(state["seen"]) < state["limit"]:
        phase = state["phase"]
        # The finite quota pass advances skipped families but stops before irrelevant mate fill.
        decision = action(state, phase, summary, progress["statuses"].get("prerequisite"))
        if decision == "stop":
            break
        if decision == "next":
            _advance(state)
            continue
        # Only a completed family can be published after a timeout.
        progress["checkpoint"] = (dict(state), dict(counts), len(progress["items"]))
        found, status, reason, focus, phase = _step(
            db,
            state,
            learner,
            summary,
            counts,
            corpus,
            budget,
            check if budget is not None else None,
        )
        # Keep a found item unpublished until the shared deadline check passes.
        mark(progress, state, phase, found)
        _check_completed(reason, budget, check)
        from .curriculum_prerequisite import offer_items

        # Bind the optional diagnostic only after candidate selection succeeds.
        found = offer_items(
            db, state, learner, found, phase, progress["statuses"].get("prerequisite"), check
        )
        record(state, phase, found, status, reason)
        annotate(state, phase, found)
        progress["items"].extend(found)
        progress["statuses"][phase] = status
        progress["focuses"][phase] = focus
        if _fill_quota(state, reason, found):
            progress["reason"] = None
            continue
        reason = classify_reason(state, reason)
        progress["reason"] = reason
        if reason is not None or _finished(state, phase):
            break
        _advance(state)


# Each successful item in final fill is its own durable cursor checkpoint.
# Earlier cursor versions keep their original repeated-fill behavior.
def _fill_quota(state, reason, found):
    if reason != "family_quota_complete":
        return False
    return not found if state["v"] in {5, 6, 8} else state["family_index"] == 3


def _finished(state, phase):
    return (state["v"] in {5, 6, 8} and phase == "new") or (
        state["v"] not in {5, 6, 8} and state["family_index"] == 3
    )


# Do not publish a just-completed item after its shared deadline.
def _check_completed(reason, budget, check):
    if budget is not None and reason in {None, "family_quota_complete"}:
        check()


def _common(db, state, learner, counts, budget, check):
    from .curriculum_priority_cursor import COMMON_POLICY

    if state.get("priority_policy") != COMMON_POLICY or state["phase"] not in {"capture", "fork"}:
        return None
    from .curriculum_common_choice import stage

    return stage(db, state, learner, counts, budget.project_root, check, budget.common_choice)
