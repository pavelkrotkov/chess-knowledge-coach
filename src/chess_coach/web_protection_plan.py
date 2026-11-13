"""Show a bounded private prepared piece-protection rehearsal."""

import sqlite3

from flask import Blueprint, current_app, render_template

from .fork_plan_action import recommendation as fork_recommendation
from .next_focus_select import choose, needs_fork
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .plan_capture_action import admissible
from .protection_plan import report
from .protection_plan_history import optional as protection_history
from .protection_progress_game import report as progress_report
from .tactical_course_budget import PreviewUnavailable
from .web_db import database

protection_plan = Blueprint("protection_plan", __name__)


@protection_plan.get("/plan/protection")
def show():
    try:
        result = report(database(), current_app.config["SUBJECT"])
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        result = None
    assessment = protection_history(
        database(), current_app.config["SUBJECT"], current_app.config["CORPUS"], result
    )
    return render_template(
        "protection_plan.html",
        report=result,
        assessment=assessment,
        protection_version=PROTECTION_VERSION,
    )


@protection_plan.get("/plan/protection/progress")
def progress():
    result, games = progress_report(
        database(),
        current_app.config["SUBJECT"],
        current_app.config["CORPUS"],
        current_app.config["PROJECT_ROOT"],
    )
    return render_template("protection_progress.html", report=result, games=games)


@protection_plan.get("/plan/next-focus")
def next_focus():
    db = database()
    subject = current_app.config["SUBJECT"]
    context = current_focus(db, subject, current_app.config["CORPUS"])

    return render_template(
        "next_focus.html",
        **context,
        protection_version=PROTECTION_VERSION,
    )


def current_focus(db, subject, corpus, *, include_optional=True):
    try:
        return _current_focus(db, subject, corpus, include_optional)
    except sqlite3.Error:
        return _unavailable()


def _current_focus(db, subject, corpus, include_optional):
    # Independent family checks must describe one unchanged database generation.
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    capture = admissible(db, subject, corpus)
    try:
        protection = report(db, subject)
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        protection = None
    assessment = protection_history(db, subject, corpus, protection)
    initial = choose(capture, protection, assessment, None)
    fork = None
    if include_optional or needs_fork(initial, capture, assessment):
        fork = fork_recommendation(db, subject, corpus)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        return _unavailable()
    selected, rotated_from = choose(capture, protection, assessment, fork)
    return {
        "capture": capture,
        "protection": protection,
        "fork": fork,
        "assessment": assessment,
        "selected": selected,
        "rotated_from": rotated_from,
    }


def _unavailable():
    return {
        "capture": None,
        "protection": None,
        "fork": None,
        "assessment": {"status": "unknown"},
        "selected": None,
        "rotated_from": None,
    }
