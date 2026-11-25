"""Join current bounded admission, conditional fit and proved practice evidence."""

from .opening_revision_candidates import initial
from .opening_revision_detail import ERRORS, annotate
from .opening_revision_inputs import comparisons
from .opening_revision_rank import selected


def judgments(db, root, learner, report):
    nomination = report.get("fork_nomination", {})
    if nomination.get("status") not in {"supported", "provisional"} or not report.get("branch"):
        return {"status": "withheld", "reason": "current_fork_nomination_unavailable"}
    decision = {**report["branch"]["exemplar"], "color": report["branch"]["color"]}
    budget = report["_budget"]
    try:
        states = comparisons(db, root, learner, decision, budget)
        rows = initial(decision, states)
        if sum(row["admission"]["status"] == "eligible" for row in rows) < 2:
            return {
                "status": "withheld",
                "reason": "fewer_than_two_admitted_alternatives",
                "alternatives": rows,
            }
        owned, public = annotate(db, root, learner, report, nomination, decision, rows)
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != report["_version"]:
            raise ValueError("opening sample changed")
        return {
            "status": "checked",
            "alternatives": rows,
            "owned_style": owned,
            "public_style": public,
            "fit": selected(rows, "fit"),
            "development": selected(rows, "development"),
        }
    except ERRORS:
        return {"status": "withheld", "reason": "source_or_deadline"}
