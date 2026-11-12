"""Explicitly find a current role- and difficulty-matched protection follow-up."""

import sqlite3
import time

from .protection_followup_context import candidate
from .protection_followup_prior import prior
from .related_capture import _assessment_options, present
from .related_capture_assessment import setup
from .related_protection import selection

SECONDS = 40.0


def matches(db, item, expected):
    try:
        return candidate(db, item) == expected
    except (ValueError, TypeError, KeyError, IndexError):
        return False


# Assessment admission requires a resettable history as well as matching roles.
def eligible(db, item, expected):
    if not matches(db, item, expected):
        return False
    try:
        setup(db, item["version"], item["key"])
        return True
    except (ValueError, TypeError, KeyError, IndexError):
        return False


# One data version covers prior validation, bounded selection and page construction.
def find(db, subject, corpus, evidence, attempt, cursor):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    expected = prior(db, subject, corpus, evidence, attempt)
    until = time.monotonic() + SECONDS
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:

        def check():
            if time.monotonic() >= until:
                raise ValueError("protection search timed out")

        chosen = selection(db, subject, evidence, corpus, check=check)
        if chosen is None:
            raise ValueError("protection search unavailable")
        filtered = []
        for item in chosen[3]:
            check()
            if eligible(db, item, expected):
                filtered.append(item)
        result = present((*chosen[:3], filtered, *chosen[4:]), cursor)
        _assessment_options(db, result["items"], filtered, cursor, result["scope"])
        result.update(
            source_outcome=chosen[0]["outcome"],
            protection_scan=chosen[2]["protection_scan"],
            corpus_limited=chosen[2]["limited"],
            followup_attempt=attempt,
        )
        check()
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("protection search changed")
        return result
    except sqlite3.OperationalError as error:
        if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise ValueError("protection search timed out") from None
        raise
    finally:
        db.connection.set_progress_handler(None, 0)
