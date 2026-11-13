"""Persist the alternating deep lanes and their bounded unfinished work."""

import json

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .pipeline_cursor import save_cursor
from .pipeline_deep_lane_validate import valid


def _key(learner):
    return digest("automatic-deep-lanes-v1:" + learner_key(learner))


def _initial(per_game=None):
    return {
        "version": 1,
        "per_game": per_game,
        "next_recent": False,
        "after": None,
        "archive": None,
        "recent": None,
    }


def load(db, learner):
    row = db.connection.execute(
        "SELECT scan_hash FROM pipeline_cursors WHERE account_key=?", (_key(learner),)
    ).fetchone()
    try:
        state = json.loads(row[0]) if row else None
        return state if valid(state) else _initial()
    except (ValueError, TypeError):
        return _initial()


def save(db, learner, state):
    save_cursor(db, _key(learner), 0, canonical(state))


def claim(db, learner, per_game):
    state = load(db, learner)
    if state.get("per_game") != per_game:
        state = _initial(per_game)
    lane = "recent" if state["next_recent"] else "archive"
    state["next_recent"] = not state["next_recent"]
    save(db, learner, state)
    return lane, state
