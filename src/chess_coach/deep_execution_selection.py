"""Authorize one current selection without exposing learner identifiers."""

from .deep_selection_source import learner_key
from .deep_selection_views import show_selection


def current_selection(db, selection_id, learner):
    key = learner_key(learner)
    row = db.connection.execute(
        "SELECT game_id FROM deep_selection_runs WHERE id=? AND learner_key=?", (selection_id, key)
    ).fetchone()
    if row is None:
        raise ValueError("selection is unavailable")
    result = show_selection(db, row["game_id"], learner, selection_id=selection_id)
    if result["state"] != "current":
        raise ValueError("selection is not current")
    return result
