"""Show and explicitly save a private coaching preview."""

from flask import Blueprint, abort, current_app, redirect, render_template, url_for

from .coaching_practice import choices
from .coaching_report import VERSION, report
from .lesson_history import save
from .web_board import board_rows
from .web_db import database
from .web_study_status import status as study_status

coaching_views = Blueprint("coaching_views", __name__)


@coaching_views.get("/coaching")
def index():
    try:
        db = database()
        preview = report(db, current_app.config["SUBJECT"])
        practice = choices(db, current_app.config["SUBJECT"], preview)
    except ValueError:
        abort(400, "Coaching preview unavailable.")
    return render_template(
        "coaching.html",
        preview=preview,
        record=None,
        board_rows=board_rows,
        practice=practice,
        study_status=study_status(current_app.config["PROJECT_ROOT"]),
    )


@coaching_views.post("/coaching/save")
def save_preview():
    db = database()
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        preview = report(db, current_app.config["SUBJECT"])
        identifier = save(db, current_app.config["SUBJECT"], preview, prompt_version=VERSION)
        db.connection.commit()
    except (ValueError, TypeError, KeyError):
        db.connection.rollback()
        abort(400, "Coaching preview unavailable; try again.")
    return redirect(url_for("lesson_views.show", lesson_id=identifier), code=303)
