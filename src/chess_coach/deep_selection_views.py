"""Read selection summaries without exposing learner or source fingerprints."""

import json

from .deep_selection_source import learner_key
from .deep_selection_view_items import selection_items, selection_state


def list_selections(db, learner, *, limit=25):
    if not 1 <= limit <= 100:
        raise ValueError("invalid selection list limit")
    key = learner_key(learner)
    rows = db.connection.execute(
        """SELECT c.game_id, r.id, r.created_at FROM deep_selection_current c
        JOIN deep_selection_runs r ON r.id=c.selection_id WHERE c.learner_key=?
        ORDER BY r.id DESC LIMIT ?""",
        (key, limit),
    ).fetchall()
    return [
        {"game_id": row["game_id"], "selection_id": row["id"], "created_at": row["created_at"]}
        for row in rows
    ]


def show_selection(db, game_id, learner, *, selection_id=None, _history=None, _position_id=None):
    key = learner_key(learner)
    current = db.connection.execute(
        "SELECT selection_id FROM deep_selection_current WHERE game_id=? AND learner_key=?",
        (game_id, key),
    ).fetchone()
    if current is None:
        raise ValueError("selection is unavailable")
    target = current["selection_id"] if selection_id is None else selection_id
    run = db.connection.execute(
        "SELECT * FROM deep_selection_runs WHERE id=? AND game_id=? AND learner_key=?",
        (target, game_id, key),
    ).fetchone()
    if run is None:
        raise ValueError("selection is unavailable")
    state = selection_state(
        db,
        game_id,
        learner,
        current["selection_id"],
        run,
        _history=_history,
        _position_id=_position_id,
    )
    items = selection_items(db, run["id"], state)
    history = db.connection.execute(
        "SELECT id,created_at FROM deep_selection_runs WHERE game_id=? AND learner_key=? ORDER BY id DESC LIMIT 100",
        (game_id, key),
    ).fetchall()
    return {
        "game_id": game_id,
        "selection_id": run["id"],
        "cheap_run_id": run["cheap_run_id"],
        "selector_version": run["selector_version"],
        "created_at": run["created_at"],
        "state": state,
        "config": json.loads(run["config_json"]),
        "coverage": json.loads(run["coverage_json"]),
        "items": items,
        "history": [
            {"selection_id": row["id"], "created_at": row["created_at"]} for row in history
        ],
    }
