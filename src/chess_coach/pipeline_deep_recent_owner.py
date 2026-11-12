"""Verify bounded recent sources before deep selection."""

from .learner_identity import normalize_identity
from .opening_explore_guard import require_bounded
from .opening_explore_recent_sql import load
from .style_time_candidates import verified


def owned(db, config, item):
    subject = normalize_identity(config.learner)
    try:
        require_bounded(db, item["id"])
    except ValueError:
        return False
    row = load(db.connection, item["id"])
    game = db.connection.execute("SELECT variant FROM games WHERE id=?", (item["id"],)).fetchone()
    return bool(
        row
        and row["pgn"] is not None
        and verified(row, subject)
        and row["projected_start"] == item["started"]
        and game
        and game["variant"] == "Standard"
    )
