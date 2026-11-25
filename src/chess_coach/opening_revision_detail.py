"""Attach bounded source evidence and preparation to admitted choices."""

import sqlite3

from .opening_preparation import report as preparation
from .opening_revision_evidence import candidate
from .opening_revision_inputs import center
from .opening_revision_rank import fit
from .style_schedule_budget import BudgetExceeded
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline

ERRORS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
    sqlite3.Error,
    TimeoutError,
    BudgetExceeded,
    PreviewUnavailable,
    PreviewDeadline,
)


def development(db, root, learner, decision, row, budget):
    try:
        witness = candidate(db, root, learner, decision, row["choice"]["uci"], budget)
    except ERRORS:
        witness = None
    if witness is None:
        return {"status": "unknown", "reason": "current_candidate_certificate_unavailable"}
    status = "supported" if witness["coverage_complete"] else "provisional"
    return {"status": status, "source": witness, "selection": row["choice"]["uci"]}


def inventory(db, root, learner, decision, row, budget):
    try:
        _, _, _, result = preparation(
            db,
            root,
            learner,
            decision["game_id"],
            decision["position_id"],
            row["choice"]["uci"],
            deadline=budget.expires,
        )
        return result
    except ERRORS:
        return {"status": "unknown", "reason": "preparation_unavailable"}


def annotate(db, root, learner, report, nomination, decision, rows):
    budget = report["_budget"]
    moves = [decision["played_uci"], *(row["choice"]["uci"] for row in rows)]
    try:
        owned, public = center(
            db, root, learner, decision, moves, nomination["nominal_control"], budget
        )
    except ERRORS:
        owned, public = {"status": "unavailable"}, {}
    for row in rows:
        if row["admission"]["status"] != "eligible":
            continue
        row["fit"] = fit(decision, row, owned, public, nomination["nominal_control"])
        row["development"] = development(db, root, learner, decision, row, budget)
        if nomination["status"] == "provisional" and row["development"]["status"] == "supported":
            row["development"]["status"] = "provisional"
        row["preparation"] = inventory(db, root, learner, decision, row, budget)
    return owned, public
