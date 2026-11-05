"""Store material recency progress in the existing private cursor table."""

import json

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical, digest
from .material_recent_state import initial
from .material_recent_validate import valid
from .pipeline_cursor import save_cursor


def _key(learner):
    return digest("recent-material-cursor-v1:" + learner_key(learner))


def load(db, learner):
    row = db.connection.execute(
        "SELECT scan_hash FROM pipeline_cursors WHERE account_key=?", (_key(learner),)
    ).fetchone()
    try:
        state = json.loads(row["scan_hash"]) if row else None
        if valid(state):
            return state
    except (ValueError, TypeError):
        pass
    return initial()


def save(db, learner, state):
    save_cursor(db, _key(learner), 0, canonical(state))


def claim(db, learner, state, *, next_recent):
    state = {**state, "next_recent": next_recent}
    save(db, learner, state)
    return state
