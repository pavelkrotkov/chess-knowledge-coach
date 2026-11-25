"""Join current owned observations to one source-bound fork certificate."""

from .opening_fork_nomination_check import binding_control, summary
from .opening_fork_nomination_owned import observations
from .opening_fork_nomination_source import source


def join(db, root, learner, report, branch, games):
    budget = report["_budget"]
    items = observations(db, learner, games, budget)
    if items is None:
        return {"status": "withheld", "reason": "evidence_unavailable_or_conflicting"}
    result = summary(items, binding_control(db, branch["exemplar"]["game_id"], budget))
    if result["status"] == "withheld":
        return result
    witness = source(db, root, learner, branch, branch["exemplar"]["catalog"]["items"], budget)
    if witness is None:
        return {"status": "withheld", "reason": "current_public_fork_unavailable"}
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != report["_version"]:
        return {"status": "withheld", "reason": "source_changed"}
    if not witness["coverage_complete"]:
        result["status"] = "provisional"
    return {
        **result,
        "branch": branch["exemplar"]["played_uci"],
        "source": witness,
    }
