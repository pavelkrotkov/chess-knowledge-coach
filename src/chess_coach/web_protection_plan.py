"""Show a bounded private prepared piece-protection rehearsal."""

import sqlite3

from flask import Blueprint, current_app, render_template

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
