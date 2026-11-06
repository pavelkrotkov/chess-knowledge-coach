"""Resolve one experiment against current owned source and queue evidence."""

from .opening_decision import inspect
from .opening_experiment import qualified
from .opening_queue_view import statuses


def current(db, root, learner, game_id, position_id, move):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    decision = inspect(db, game_id, position_id, learner)
    choice = next((item for item in decision["catalog"]["items"] if item["uci"] == move), None)
    if choice is None:
        raise ValueError("opening alternative unavailable")
    selected = {**decision, "catalog": {**decision["catalog"], "items": [choice]}}
    result = statuses(db, root, learner, selected).get(move, {})
    experiment = qualified(decision, choice, result)
    if experiment is None or db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("opening experiment unavailable or changed")
    return decision, choice, experiment
