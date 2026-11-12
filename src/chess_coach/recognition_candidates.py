"""Choose one bounded, source-bound unfamiliar recognition prompt."""

import sqlite3
import time

from .learner_identity import normalize_identity
from .recognition_scan import scan
from .related_capture_familiar import familiarity

SECONDS = 25.0


def choose(db, subject, version):
    until = time.monotonic() + SECONDS
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        return _choose(db, subject, version, until)
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise ValueError("recognition search deadline reached") from None
        raise
    finally:
        db.connection.set_progress_handler(None, 0)


def _choose(db, subject, version, until):
    identity = normalize_identity(subject)
    if not identity:
        raise ValueError("recognition subject unavailable")
    initial = db.connection.execute("PRAGMA data_version").fetchone()[0]

    def check():
        if time.monotonic() >= until:
            raise ValueError("recognition search deadline reached")

    familiar, games, seen = familiarity(db, subject, check=check)
    corpus = db.connection.execute(
        "SELECT id FROM puzzle_corpora WHERE version=? AND state='ready'", (version,)
    ).fetchone()
    if corpus is None:
        raise ValueError("recognition corpus unavailable")
    candidate = scan(db, subject, version, corpus["id"], familiar, games, seen, check)
    check()
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != initial:
        raise ValueError("recognition sources changed")
    if candidate:
        return candidate, initial
    raise ValueError("no supported unfamiliar recognition prompt in the bounded sample")
