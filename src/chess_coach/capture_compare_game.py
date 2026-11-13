"""Read matching capture practice and independent dated game windows."""

from .capture_compare_report import report as practice_report
from .mastery_time import parse_utc
from .recognition_progress_game import capture


def relation(practice, games):
    if practice.get("status") != "comparable" or not practice.get("answer_end"):
        return "practice_unavailable"
    if not games or not games.get("comparable"):
        return "games_unavailable"
    if any(games[name]["unchecked"] for name in ("earlier", "newer")):
        return "games_incomplete"
    return _dates(games["earlier"].get("oldest"), practice["answer_end"])


def _dates(game_start, practice_end):
    start, end = parse_utc(game_start), parse_utc(practice_end)
    if not start or not end:
        return "dates_unavailable"
    return "later" if start > end else "overlap"


def report(db, subject, corpus, root):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    practice = practice_report(db, subject, corpus)
    games = capture(db, subject, root)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("capture comparison changed")
    return practice, games, relation(practice, games)
