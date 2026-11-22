"""Resolve one experiment against current owned source and queue evidence."""

from .opening_decision import inspect
from .opening_experiment import qualified
from .opening_queue_view import statuses


# Reuse the caller's budget so a shared snapshot never installs a nested handler.
def _decision(db, game_id, position_id, learner, move, deadline, budget):
    if deadline is None and budget is None:
        return inspect(db, game_id, position_id, learner, alternative=move)
    if budget is None:
        from .opening_queue_budget import BrowserBudget

        budget = BrowserBudget(db)
    if deadline is not None:
        budget.expires = min(budget.expires, deadline)
    with budget.scope(snapshot=False):
        return inspect(db, game_id, position_id, learner, alternative=move)


def _options(with_identity, deadline, budget):
    options = {"with_identity": True} if with_identity else {}
    if deadline is not None:
        options["deadline"] = deadline
    if budget is not None:
        options["budget"] = budget
    return options


def current(
    db,
    root,
    learner,
    game_id,
    position_id,
    move,
    *,
    with_identity=False,
    deadline=None,
    budget=None,
):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    decision = _decision(db, game_id, position_id, learner, move, deadline, budget)
    choice = next((item for item in decision["catalog"]["items"] if item["uci"] == move), None)
    if choice is None:
        raise ValueError("opening alternative unavailable")
    selected = {**decision, "catalog": {**decision["catalog"], "items": [choice]}}
    result = statuses(db, root, learner, selected, **_options(with_identity, deadline, budget)).get(
        move, {}
    )
    experiment = qualified(decision, choice, result)
    if experiment is None or db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("opening experiment unavailable or changed")
    if with_identity:
        return decision, choice, experiment, result["_identity"]
    return decision, choice, experiment
