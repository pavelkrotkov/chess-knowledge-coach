"""Derive held-out eligibility without changing the recorded assessment."""

from .related_capture_position import prompt_key
from .tactical_exposure_check import check


def status(db, row, answered_at):
    return check(db, row["subject"], prompt_key(row["prompt_fen"]), answered_at=answered_at)


def qualifying(db, row, result, answered_at):
    if result not in {"correct", "incorrect", "unresolved"} or not answered_at:
        return result, None
    reason = status(db, row, answered_at)
    return (result, None) if reason == "not_recorded" else ("not_held_out", reason)


def apply(db, row, state):
    grade = state["status"]
    heldout, reason = qualifying(db, row, grade, state.get("answered_at"))
    return {**state, "status": heldout, "grade": grade, "eligibility_reason": reason}
