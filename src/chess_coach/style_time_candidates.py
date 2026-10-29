"""Bounded index lookups before replaying any game or decision."""

from .learner_identity import learner_color, normalize_identity
from .repertoire_limit import validate_limit
from .style_time_projection import projection
from .style_time_query import load_game, side_candidates
from .style_time_uncertainty import uncertain_count


def verified(row, subject):
    if row is None:
        return None
    values = projection(row)
    expected = ("current", row["projected_start"], row["projected_white"], row["projected_black"])
    if values[1:] != expected:
        return None
    return learner_color(row, subject)


def recent_games(db, learner, *, limit):
    validate_limit(limit)
    subject = normalize_identity(learner)
    if subject is None:
        raise ValueError("learner identity is unavailable")
    connection = db.connection
    candidates = side_candidates(connection, subject, "white", limit)
    candidates += side_candidates(connection, subject, "black", limit)
    candidates.sort(key=lambda row: (row["started_at"], row["game_id"]), reverse=True)
    chosen = candidates[:limit]
    loaded = (load_game(connection, item["game_id"]) for item in chosen)
    games = [(row, color) for row in loaded if (color := verified(row, subject))]
    unknown_time, unknown_owner = uncertain_count(connection, subject, limit)
    return games, {
        "game_limit_reached": len(candidates) > limit,
        "unknown_time_lower_bound": unknown_time,
        "unknown_ownership_global_lower_bound": unknown_owner,
        "candidate_recheck_failed": len(chosen) - len(games),
        "boundary_tie": len(candidates) > limit
        and candidates[limit]["started_at"] == candidates[limit - 1]["started_at"],
    }
