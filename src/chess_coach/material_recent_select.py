"""Choose current analyzed owned games in verified played-time order."""

from .learner_identity import normalize_identity
from .material_recent_cursor import save
from .material_recent_source import eligible
from .material_recent_state import WINDOW, finished, initial
from .pipeline_recent_rows import rows


def choose(db, config, engine_hash, state, report):
    learner = config.learner
    identity = normalize_identity(learner)
    if state["within"]:
        report["games_examined"] += 1
        item = {"started_at": state["after"][0], "game_id": state["after"][1]}
        try:
            if eligible(db, identity, item, config, engine_hash):
                return item, state
        except (ValueError, TypeError, KeyError, IndexError):
            pass
        report["source_unavailable"] += 1
        state = finished(state)
    candidates = rows(db, identity, WINDOW - state["seen"], state["after"])
    for item in candidates[: WINDOW - state["seen"]]:
        report["games_examined"] += 1
        state = {**state, "after": [item["started_at"], item["game_id"]]}
        try:
            if eligible(db, identity, item, config, engine_hash):
                state = {**state, "within": True, "ply": 0}
                save(db, learner, state)
                return item, state
        except (ValueError, TypeError, KeyError, IndexError):
            pass
        report["source_unavailable"] += 1
        state = finished(state)
        if state["after"] is None:
            break
    state = initial(next_recent=state["next_recent"])
    save(db, learner, state)
    return None, state
