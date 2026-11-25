"""Recheck the exact inputs before returning opening revision judgments."""

from .opening_fit_later_index import locate
from .opening_fork_nomination_source import _witness
from .opening_public_proof_read import lookup
from .opening_revision_inputs import comparisons


def _proof(db, root, learner, decision, saved, branch, budget):
    proof = lookup(
        db,
        root,
        learner,
        decision["game_id"],
        decision["position_id"],
        saved["alternative"],
        budget.expires,
        fork_window=saved["window"],
    )
    if _witness(proof, decision["color"], saved["alternative"], branch=branch) != saved:
        raise ValueError("public fork evidence changed")


def confirm(db, root, learner, report, nomination, decision, rows, states, index):
    budget = report["_budget"]
    budget.check()
    if comparisons(db, root, learner, decision, budget) != states:
        raise ValueError("opening comparison changed")
    if index is not None and locate(root, learner, "recent") != index:
        raise ValueError("public opening source changed")
    _proof(db, root, learner, decision, nomination["source"], "played", budget)
    for row in rows:
        saved = row.get("development", {}).get("source")
        if saved is not None:
            budget.check()
            _proof(db, root, learner, decision, saved, "alternative", budget)
    budget.check()
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != report["_version"]:
        raise ValueError("opening sample changed")
