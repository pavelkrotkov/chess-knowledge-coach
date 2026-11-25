"""Offer an optional mate diagnostic for a witnessed back-rank topic."""

from .curriculum_prerequisite_mate import retry_unavailable
from .curriculum_prerequisite_source import context
from .curriculum_prerequisite_token import issue
from .tactical_course_budget import PreviewUnavailable


def prepare(db, state, subject, summary, check):
    if db.compat32:
        return {"state": "learning_unavailable"}
    if check is None:
        return {"state": "unavailable"}
    if state["prerequisite_deferred"]:
        return {"state": "deferred"}
    try:
        current = context(db, subject, state["scan_limit"], check)
    except PreviewUnavailable:
        state["prerequisite_deferred"] = True
        return {"state": "deferred"}
    # A continuation cannot silently change its nominated source.
    if state["prerequisite_checked"] and state["prerequisite_scope"] != current["scope"]:
        raise ValueError("prerequisite source changed; restart the plan")
    state["prerequisite_scope"] = current["scope"]
    state["prerequisite_checked"] = True
    return {
        "state": current["state"],
        "review": current.get("review"),
        "mate_evidence": _mate_evidence(summary),
    }


def _mate_evidence(summary):
    if summary["source_scan_incomplete"] or summary["state"] == "cold_start":
        return "unknown"
    count = summary["context_count"]
    return "reviewed_sufficient" if count is not None and count >= 3 else "insufficient"


def offer(db, state, subject, item, info, check):
    if info["state"] != "available" or state["prerequisite_offered"]:
        return item
    if info["mate_evidence"] == "reviewed_sufficient":
        return item
    check()
    try:
        token = issue(db, state, subject, item)
    except (ValueError, TypeError, KeyError, IndexError):
        info["diagnostic"] = "unavailable"
        return item
    check()
    info.pop("diagnostic", None)
    state["prerequisite_offered"] = True
    return {
        **item,
        "unified_training": True,
        "prerequisite_token": token,
        "reason": (
            "Optional mate-in-one recognition practice related to a current back-rank "
            "prevention topic. The topic remains provisional; this does not establish "
            "mastery or explain a game decision. Other exposure history may be unknown."
        ),
    }


def offer_items(db, state, subject, found, phase, info, check):
    if phase != "new" or state["v"] not in {4, 5, 6, 8} or not found:
        return found
    result = [offer(db, state, subject, item, info, check) for item in found]
    return [] if retry_unavailable(state, result, info) else result
