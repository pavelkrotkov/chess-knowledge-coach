"""Recheck current first-encounter and source-game familiarity."""

import sqlite3
import time

from .learner_identity import normalize_identity
from .recognition_exposures import source_game
from .recognition_game_frontier import new_initials
from .related_capture_probe import position_probe
from .related_protection_later_exposure import require_unexposed

SECONDS = 2.0


def novel(db, row):
    until = time.monotonic() + SECONDS
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        _novel(db, row, until)
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise ValueError("recognition familiarity deadline reached") from None
        raise
    finally:
        db.connection.set_progress_handler(None, 0)


def _novel(db, row, until):
    def check():
        if time.monotonic() >= until:
            raise ValueError("recognition familiarity deadline reached")

    subject = row["subject"]
    source_game(db, row, check)
    new_initials(db, row, check)
    probe = position_probe(
        db, normalize_identity(subject), subject, exclude_recognition=row["attempt_id"]
    )
    if probe(row["prompt_key"]):
        raise ValueError("recognition prompt became familiar")
    require_unexposed(db, row, row["prompt_key"], check)
    check()
