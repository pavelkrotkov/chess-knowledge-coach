"""Build bounded first-encounter history under one source generation."""

import sqlite3
import time

from .recognition_progress_gather import collect

SECONDS = 10.0


def report(db, subject, corpus):
    until = time.monotonic() + SECONDS
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        result = collect(db, subject, corpus, until)
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("recognition sources changed")
        return result
    except (sqlite3.OperationalError, ValueError):
        return None
    finally:
        db.connection.set_progress_handler(None, 0)
