"""Show a bounded private prepared piece-protection rehearsal."""

import sqlite3

from flask import Blueprint, current_app, render_template

from .fork_plan_action import recommendation as fork_recommendation
from .plan_capture_action import admissible
from .protection_plan import report
from .tactical_course_budget import PreviewUnavailable
from .web_db import database

protection_plan = Blueprint("protection_plan", __name__)


@protection_plan.get("/plan/protection")
def show():
    try:
        result = report(database(), current_app.config["SUBJECT"])
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        result = None
    return render_template("protection_plan.html", report=result)


@protection_plan.get("/plan/next-focus")
def next_focus():
    db = database()
    subject = current_app.config["SUBJECT"]
    capture = admissible(db, subject, current_app.config["CORPUS"])
    try:
        protection = report(db, subject)
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        protection = None
    selected = _focus(capture, protection)
    fork = fork_recommendation(db, subject, current_app.config["CORPUS"])
    return render_template(
        "next_focus.html", capture=capture, protection=protection, selected=selected, fork=fork
    )


def _focus(capture, protection):
    source = protection and protection["source"]
    if not source:
        return "capture" if capture else None
    if not capture:
        return "protection"
    history = capture["history"]
    if history["status"] == "correct" and history.get("assistance") == "unassisted":
        return "protection"
    return "protection" if source["games"] > capture["source"]["games"] else "capture"
