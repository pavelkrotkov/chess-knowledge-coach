"""Read-only descriptive repertoire over current classifications."""

from .opening_snapshot import SOURCE, VERSION
from .repertoire_game import game_detail as game_detail
from .repertoire_game import game_report
from .repertoire_groups import groups
from .repertoire_recurring import recurring
from .repertoire_sources import games_for_learner


def repertoire_report(db, learner):
    rows, game_limit, scan_limit = games_for_learner(db, learner)
    games = [game_report(db, game, color, learner) for game, color in rows]
    dataset = db.connection.execute(
        "SELECT id,version,source_url,content_revision FROM opening_datasets WHERE version=? AND source_url=?",
        (VERSION, SOURCE),
    ).fetchone()
    return {
        "dataset": dict(dataset) if dataset else None,
        "expected_dataset": {"version": VERSION, "source_url": SOURCE},
        "games": games,
        "game_limit_reached": game_limit,
        "scan_limit_reached": scan_limit,
        "position_limit_games": sum(g["positions_truncated"] for g in games),
        "unclassified": sum(g["opening"] is None for g in games),
        "stale": sum(g["classification_stale"] for g in games),
        "unknown": sum(bool(g["opening"]) and not g["opening"]["position_key"] for g in games),
        "groups": groups(games),
        "recurring": recurring(games),
    }
