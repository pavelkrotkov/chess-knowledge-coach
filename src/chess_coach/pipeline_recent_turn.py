"""Keep recent rotation and single-lane turns across worker restarts."""

import json

from .fact_fingerprint import canonical, digest
from .lichess_state import account_key
from .pipeline_cursor import save_cursor
from .pipeline_recent_state import initial, valid


def _key(learner):
    return digest("recent-ordinary-analysis-turn-v1:" + account_key(learner.strip()))


def _read(db, learner):
    row = db.connection.execute(
        "SELECT last_game_id,scan_hash FROM pipeline_cursors WHERE account_key=?",
        (_key(learner),),
    ).fetchone()
    try:
        state = json.loads(row["scan_hash"]) if row else {}
        if valid(state):
            return row["last_game_id"] == 1, state
    except (ValueError, TypeError, AttributeError):
        pass
    return False, initial()


def recent_turn(db, learner):
    return _read(db, learner)[0]


def progress(db, learner):
    return _read(db, learner)[1]


def claim(db, learner, *, next_recent):
    _, state = _read(db, learner)
    save_cursor(db, _key(learner), int(next_recent), canonical(state))


def advance(db, learner, state):
    next_recent, _ = _read(db, learner)
    save_cursor(db, _key(learner), int(next_recent), canonical(state))
