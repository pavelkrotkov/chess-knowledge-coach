"""Private read-only matched recognition and independent game coverage."""

from flask import Blueprint, current_app, render_template

from .recognition_progress_game import capture, later
from .recognition_progress_history import report
from .web_db import database

recognition_progress = Blueprint("recognition_progress", __name__)


@recognition_progress.get("/recognition/progress")
def show():
    db = database()
    subject = current_app.config["SUBJECT"]
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    result = report(db, subject, current_app.config["CORPUS"])
    games = capture(db, subject, current_app.config["PROJECT_ROOT"])
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        result, games = None, None
    return render_template("recognition_progress.html", report=result, games=games, later=later)
