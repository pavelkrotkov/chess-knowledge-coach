"""Offer a bounded source-checked pin-defense practice choice."""

import sqlite3

from flask import Blueprint, current_app, render_template

from .pin_plan import report
from .tactical_course_budget import PreviewUnavailable
from .web_db import database

pin_plan = Blueprint("pin_plan", __name__)


@pin_plan.get("/plan/pin-defense")
def show():
    try:
        result = report(database(), current_app.config["SUBJECT"])
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        result = None
    return render_template("pin_plan.html", report=result)
