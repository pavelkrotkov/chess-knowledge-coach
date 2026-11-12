"""Find the next bounded, verified recent owned game for normal deep work."""

from .learner_identity import normalize_identity
from .pipeline_deep_lane_validate import WINDOW
from .pipeline_recent_rows import rows


def next_game(db, config, state):
    subject = normalize_identity(config.learner)
    candidates = rows(db, subject, WINDOW, None)[:WINDOW]
    anchor = tuple(state["after"]) if state["after"] else None
    keys = [(item["started_at"], item["game_id"]) for item in candidates]
    index = keys.index(anchor) + 1 if anchor in keys else 0
    if index >= len(candidates):
        return None, {**state, "after": None}, False
    item = candidates[index]
    more = index + 1 < len(candidates)
    after = [item["started_at"], item["game_id"]] if more else None
    state = {**state, "after": after}
    return (
        {"id": item["game_id"], "started": item["started_at"], "attempts": 0},
        state,
        more,
    )
