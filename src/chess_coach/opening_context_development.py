"""Order unfamiliar choices by independently reviewed learning evidence."""

import sqlite3

from .opening_context_development_owned import collect
from .opening_context_development_partition import partition
from .opening_fit import RESERVE
from .style_schedule_budget import BudgetExceeded
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline


def assess(db, learner, color, games, group, budget, incomplete):
    eligibility = group["fit"]["choices"]
    admitted = sum(value == "admitted" for value in eligibility.values())
    result = partition(group["items"], eligibility, color)
    if admitted < 2:
        return {**result, "status": "withheld", "reason": "fewer_than_two_admitted"}
    if not result["proved"]:
        return {
            **result,
            "status": "withheld",
            "reason": "current_material_certificate_unavailable",
        }
    if incomplete:
        return {**result, "status": "withheld", "reason": "owned_history_incomplete"}
    original = budget.expires
    budget.expires = original - RESERVE
    try:
        owned = collect(db, learner, games, color, budget)
        if owned["status"] != "supported":
            return {**result, "status": "withheld", "reason": owned["reason"], "owned": owned}
        result["eligible"] = result["proved"]
        if len(result["eligible"]) > 1:
            return {**result, "status": "tie", "reason": "multiple_proved_examples", "owned": owned}
        return {
            **result,
            "status": "provisional",
            "choice": result["eligible"][0],
            "owned": owned,
            "reason": "proved_example_with_incomplete_wider_public_coverage",
        }
    except (
        PreviewUnavailable,
        PreviewDeadline,
        BudgetExceeded,
        TimeoutError,
        OSError,
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
    ):
        return {**result, "status": "withheld", "reason": "evidence_unavailable"}
    finally:
        budget.expires = original
