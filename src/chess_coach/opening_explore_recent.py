"""Select the recent sample without materializing oversized game text."""

from .learner_identity import normalize_identity
from .opening_explore_recent_sql import load as _load
from .style_time_candidates import verified
from .style_time_query import side_candidates
from .style_time_uncertainty import uncertain_count

LIMIT = 100


def recent(db, learner):
    subject = normalize_identity(learner)
    if subject is None:
        raise ValueError("learner identity is unavailable")
    connection = db.connection
    candidates = side_candidates(connection, subject, "white", LIMIT)
    candidates += side_candidates(connection, subject, "black", LIMIT)
    candidates.sort(key=lambda row: (row["started_at"], row["game_id"]), reverse=True)
    chosen = candidates[:LIMIT]
    games, oversized = [], 0
    for item in chosen:
        row = _load(connection, item["game_id"])
        if row is not None and row["pgn"] is None:
            oversized += 1
            continue
        color = verified(row, subject)
        if color:
            games.append(({"id": row["id"], "projected_start": row["projected_start"]}, color))
    unknown_time, unknown_owner = uncertain_count(connection, subject, LIMIT)
    return games, {
        "game_limit_reached": len(candidates) > LIMIT,
        "unknown_time_lower_bound": unknown_time,
        "unknown_ownership_global_lower_bound": unknown_owner,
        "candidate_recheck_failed": len(chosen) - len(games),
        "oversized_pgn": oversized,
        "boundary_tie": len(candidates) > LIMIT
        and candidates[LIMIT]["started_at"] == candidates[LIMIT - 1]["started_at"],
    }
