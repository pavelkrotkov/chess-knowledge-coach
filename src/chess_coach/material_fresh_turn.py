"""Persist fresh-pass position and alternate it with the recent rotation."""

import json

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .material_fresh_validate import valid
from .pipeline_cursor import save_cursor


def _key(learner):
    return digest("material-fresh-turn-v1:" + learner_key(learner))


def _initial(next_fresh=False):
    return {"version": 2, "next_fresh": next_fresh, "last": 0, "positions": []}


def load(db, learner):
    row = db.connection.execute(
        "SELECT scan_hash FROM pipeline_cursors WHERE account_key=?", (_key(learner),)
    ).fetchone()
    raw = row[0] if row else None
    try:
        state = json.loads(raw) if raw else None
        return state if valid(state) else _initial()
    except (TypeError, ValueError):
        return _initial()


def save(db, learner, state):
    save_cursor(db, _key(learner), 0, canonical(state))


def claim(db, learner):
    state = load(db, learner)
    fresh = state["next_fresh"]
    state = {**state, "next_fresh": not fresh}
    save(db, learner, state)
    return fresh, state
