"""Request local preparation of a current tactical course."""

from pathlib import Path
from types import SimpleNamespace

from flask import abort, current_app, redirect, url_for

from .tactical_course_request import enqueue, status


def prepare():
    db = SimpleNamespace(path=Path(current_app.config["DB_PATH"]))
    try:
        enqueue(
            db,
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            current_app.config["CORPUS"],
        )
    except (OSError, ValueError, TypeError, KeyError):
        abort(409, "Course preparation is unavailable. Please try again.")
    return redirect(url_for("tactical_course_views.show"), code=303)


def preparation(offered=None):
    db = SimpleNamespace(path=Path(current_app.config["DB_PATH"]))
    return status(
        db,
        current_app.config["PROJECT_ROOT"],
        current_app.config["SUBJECT"],
        current_app.config["CORPUS"],
        offered,
    )
