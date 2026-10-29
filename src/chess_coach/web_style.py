"""Private, source-linked descriptive choice profile."""

from flask import Blueprint, current_app, render_template

from .style_report import style_report
from .web_db import database

style_views = Blueprint("style_views", __name__)


@style_views.get("/style-choices")
def style():
    try:
        report = style_report(database(), current_app.config["SUBJECT"])
    except ValueError:
        report = None
    return render_template("style_choices.html", report=report)
