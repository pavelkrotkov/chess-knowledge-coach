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
    return _dates(
        games["earlier"].get("oldest"), games["newer"].get("oldest"), practice["answer_end"]
    )


def _dates(earlier, newer, practice_end):
    old, new, end = parse_utc(earlier), parse_utc(newer), parse_utc(practice_end)
    if not old or not new or not end:
        return "dates_unavailable"
    if old > end and new > end:
        return "later"
    return "newer_only" if new > end else "overlap"


def report(db, subject, corpus, root):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    practice = practice_report(db, subject, corpus)
    games = capture(db, subject, root)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("capture comparison changed")
    return practice, games, relation(practice, games)
