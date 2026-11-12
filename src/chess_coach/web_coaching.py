"""Show and explicitly save a private coaching preview."""

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from .coaching_fork_defense import actions as defense_actions
from .coaching_practice import choices
from .coaching_quick_scope import patterns, selected
from .coaching_quick_view import preview as quick_preview
from .coaching_report import VERSION, report
from .lesson_history import save
from .tactical_study_status import status as tactical_study_status
from .web_board import board_rows
from .web_db import database
from .web_study_status import status as study_status

coaching_views = Blueprint("coaching_views", __name__)


@coaching_views.get("/coaching")
def index():
    full = request.args.get("full")
    pattern = request.args.get("pattern")
    if full not in (None, "1") or (full == "1" and pattern is not None):
        abort(400, "Coaching scope unavailable.")
    try:
        db = database()
        if full == "1":
            preview = report(db, current_app.config["SUBJECT"])
            practice = choices(db, current_app.config["SUBJECT"], preview, adaptive=True)
        else:
            preview, practice = quick_preview(db, current_app.config["SUBJECT"], selected(pattern))
    except ValueError:
        abort(400, "Coaching preview unavailable.")
    return render_template(
        "coaching.html",
        preview=preview,
        record=None,
        board_rows=board_rows,
        practice=practice,
        defenses=defense_actions(db, current_app.config["SUBJECT"], preview),
        patterns=patterns(),
        study_status=study_status(current_app.config["PROJECT_ROOT"]),
        tactical_study_status=tactical_study_status(
            current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"]
        ),
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
