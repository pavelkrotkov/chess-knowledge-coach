"""Qualify first-turn opportunity fit for a checked unfamiliar parent."""

import sqlite3

from .opening_context_fit_inputs import first_turn, reasons
from .opening_context_fit_public import opportunities
from .opening_context_fit_rank import result as compare
from .opening_fit import RESERVE, _owned_scope
from .opening_fit_owned import collect
from .style_schedule_budget import BudgetExceeded
from .tactical_course_budget import PreviewUnavailable


def _measure(db, root, subject, color, path, admitted, budget):
    with _owned_scope(db, budget):
        owned = collect(db, subject, path[0] if color == "black" else None)
    cohort = owned.get("colors", {}).get(color, {})
    if not cohort.get("positive"):
        return {"reason": "own_cohort_unqualified", "owned": cohort}
    control = cohort["time_control"]
    public, source = opportunities(root, subject, color, path, admitted, control, budget)
    return {
        **compare(admitted, public),
        "owned": cohort,
        "control": control,
        "public": public,
        "opportunity_index": source,
    }


def assess(db, root, subject, color, path, items, budget, history_ready):
    eligibility = reasons(items, history_ready)
    admitted = [item for item in items if eligibility[item["uci"]] == "admitted"]
    result = {
        "status": "withheld",
        "reason": "fewer_than_two_admitted",
        "choices": eligibility,
        "comparisons": {item["uci"]: item["comparison"]["status"] for item in items},
    }
    if len(admitted) < 2:
        return result
    if not first_turn(color, path, admitted):
        return {**result, "reason": "first_turn_context_unavailable"}
    original = budget.expires
    budget.expires = original - RESERVE
    try:
        return {**result, **_measure(db, root, subject, color, path, admitted, budget)}
    except (
        PreviewUnavailable,
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
        return {**result, "reason": "evidence_unavailable"}
    finally:
        budget.expires = original
