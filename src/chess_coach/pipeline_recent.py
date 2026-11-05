"""Choose one recent owned game requiring ordinary analysis."""

from .learner_identity import normalize_identity
from .pipeline_recent_rows import rows
from .pipeline_recent_source import eligible
from .pipeline_recent_state import WINDOW, initial, next_state
from .pipeline_recent_turn import progress
from .style_time_candidates import verified
from .style_time_query import load_game


def select(db, config, engine_hash, limit):
    stats = {
        "examined": 0,
        "selected": 0,
        "current": 0,
        "failed": 0,
        "over_budget": 0,
        "invalid": 0,
    }
    identity = normalize_identity(config.learner)
    full = limit >= WINDOW
    state = initial() if full else progress(db, config.learner)
    limit = min(limit, WINDOW - state["seen"])
    candidates = rows(db, identity, limit, state["after"])
    last = None
    for item in candidates[:limit]:
        last = [item["started_at"], item["game_id"]]
        stats["examined"] += 1
        try:
            game = load_game(db.connection, item["game_id"])
            if (
                not verified(game, identity)
                or game["variant"] != "Standard"
                or game["projected_start"] != item["started_at"]
            ):
                stats["invalid"] += 1
                continue
            selected, reason = eligible(db, game, config, engine_hash)
        except (ValueError, TypeError, KeyError, IndexError):
            stats["invalid"] += 1
            continue
        stats[reason] += 1
        if selected is not None:
            return (
                selected,
                stats,
                next_state(state, last, stats["examined"], len(candidates), full=full),
            )
    return None, stats, next_state(state, last, stats["examined"], len(candidates), full=full)
