"""Recheck first encounter and indexed learner familiarity for an assessment."""

import sqlite3
import time

from .fork_followup_first import first
from .learner_identity import normalize_identity
from .related_capture_position import prompt_key
from .related_protection_later_exposure import require_unexposed

SECONDS = 2.0


def require_novel(db, row):
    until = time.monotonic() + SECONDS
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        _check(db, row, until)
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise ValueError("protection familiarity check timed out") from None
        raise
    finally:
        db.connection.set_progress_handler(None, 0)


def _check(db, row, until):
    def check():
        if time.monotonic() >= until:
            raise ValueError("protection familiarity check timed out")

    subject = row["subject"]
    first(db, subject, row)
    key = prompt_key(row["prompt_fen"])
    if row["status"] == "active":
        require_unexposed(db, row, key, check)
    prefix = key + " "
    identity = normalize_identity(subject)
    prior = db.connection.execute(
        """SELECT 1 FROM positions p INDEXED BY idx_positions_fen_game
        JOIN games g ON g.id=p.game_id WHERE p.fen>=? AND p.fen<?
        AND (lower(g.white)=? OR lower(g.black)=?) LIMIT 1""",
        (prefix, prefix + "\uffff", identity, identity),
    ).fetchone()
    check()
    if prior:
        raise ValueError("protection assessment is familiar")
