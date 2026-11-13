"""Request publication of the exact currently offered private course."""

from pathlib import Path
from types import SimpleNamespace

from flask import abort, current_app, redirect, request, url_for

from .tactical_study_request import enqueue


def submit():
    version = request.form.get("version", "")
    db = SimpleNamespace(path=Path(current_app.config["DB_PATH"]))
    try:
        enqueue(
            db,
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            current_app.config["CORPUS"],
            version,
        )
    except (OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError):
        abort(409, "This course request is unavailable. Reopen the prepared course.")
    return redirect(url_for("tactical_course_views.show", version=version), code=303)
