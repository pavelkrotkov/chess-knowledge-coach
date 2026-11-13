"""Read verified protection assessments and independent cached game windows."""

import sqlite3

from .capture_compare_game import relation
from .learner_identity import normalize_identity
from .protection_game_report import report as game_report
from .protection_progress import report as practice_report


def report(db, subject, corpus, root):
    subject = normalize_identity(subject)
    if not subject:
        return None, None
    try:
        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        practice = practice_report(db, subject, corpus)
        games = game_report(db, subject, root)
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            return None, None
        if practice is not None:
            _relate(practice, games)
        return practice, games
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None, None


def _relate(practice, games):
    checked_games = {**games, "comparable": games["comparable_reason"] is None} if games else None
    for group in practice["groups"]:
        checked = {
            "status": "unavailable" if group.get("reason") else "comparable",
            "answer_end": group.get("answer_end"),
        }
        group["relation"] = relation(checked, checked_games)
