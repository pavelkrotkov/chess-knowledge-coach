"""Persist bounded recent discovery-defense progress per learner."""

import json

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .material_fresh_validate import valid
from .pipeline_cursor import save_cursor


def _key(learner):
    return digest("discovery-defense-recent-v1:" + learner_key(learner))


def load(db, learner):
    row = db.connection.execute(
        "SELECT scan_hash FROM pipeline_cursors WHERE account_key=?", (_key(learner),)
    ).fetchone()
    try:
        state = json.loads(row[0]) if row else None
        if valid(state):
            return state
    except (ValueError, TypeError):
        pass
    return {"version": 2, "next_fresh": True, "last": 0, "positions": []}


def save(db, learner, state):
    save_cursor(db, _key(learner), 0, canonical(state))
