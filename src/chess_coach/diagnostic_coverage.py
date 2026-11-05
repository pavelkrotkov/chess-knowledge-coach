"""Bounded played-time analysis coverage, separate from evidence selection."""

from collections import Counter

from .repertoire_limit import MAX_GAMES
from .style_time_candidates import recent_games


def diagnostic_coverage(db, learner):
    rows, time_coverage = recent_games(db, learner, limit=MAX_GAMES)
    states = Counter()
    for game, _ in rows:
        stage = db.connection.execute(
            "SELECT status FROM pipeline_stages WHERE game_id=? AND stage=?",
            (game["id"], "analysis"),
        ).fetchone()
        states[stage[0] if stage else "not analyzed"] += 1
    return {
        "examined_games": len(rows),
        "analysis_stages": dict(states),
        "game_limit_reached": time_coverage["game_limit_reached"],
        "scan_limit_reached": False,
        "time_coverage": time_coverage,
    }
