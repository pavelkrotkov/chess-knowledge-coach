"""Combine verified fork practice and current cached game windows."""

from .capture_compare_game import relation
from .fork_game_trend_report import report as game_report
from .fork_progress_report import report as practice_report


def report(db, subject, corpus, root):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    practice = practice_report(db, subject, corpus)
    games = game_report(db, subject, root)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        return {"status": "incomplete", "largest": 0}, None, "games_unavailable"
    game_ready = bool(
        games
        and not games.get("historical")
        and games.get("comparison")
        and games["comparison"]["qualified"]
    )
    checked_games = {**games, "comparable": game_ready} if games else None
    checked_practice = {
        "status": "comparable" if practice.get("answer_end") else "unavailable",
        "answer_end": practice.get("answer_end"),
    }
    return practice, games, relation(checked_practice, checked_games)
