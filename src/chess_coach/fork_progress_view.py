"""Serve the private matched fork progress report."""

import sqlite3

from flask import current_app, render_template

from .fork_progress_report import report
from .web_db import database


def show():
    try:
        result = report(database(), current_app.config["SUBJECT"], current_app.config["CORPUS"])
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return render_template(
            "error.html", message="Fork progress is unavailable or changed."
        ), 400
    return render_template("fork_progress.html", report=result)
