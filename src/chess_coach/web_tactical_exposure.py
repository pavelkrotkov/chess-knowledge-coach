"""Fail closed when served tactical material cannot be recorded."""

import sqlite3

from flask import abort, current_app

from .tactical_exposure_record import record as record_exposure
from .web_db import database


def record(artifact, chapters, kind, *, line=None):
    db = database()
    if db.compat32:
        return
    try:
        record_exposure(db, current_app.config["SUBJECT"], artifact, chapters, kind, line=line)
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, RuntimeError):
        abort(503, "The course could not be provided safely. Please try again.")
