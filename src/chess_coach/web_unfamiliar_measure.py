"""Render optional private comparison status beside unfamiliar suggestions."""

from flask import current_app, render_template, request

from .opening_unfamiliar import explore_unfamiliar
from .opening_unfamiliar_measure import measurements
from .tactical_course_deadline import PreviewDeadline
from .web_db import database


def show():
    if request.args.get("choices") == "1":
        from .opening_unfamiliar_options import group

        try:
            report, items = group(
                database(), current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"]
            )
        except (Exception, PreviewDeadline):
            return render_template(
                "error.html", message="These opening choices could not be checked now."
            ), 503
        return render_template("opening_unfamiliar_options.html", report=report, items=items)
    version = database().connection.execute("PRAGMA data_version").fetchone()[0]
    try:
        report = explore_unfamiliar(
            database(), current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"]
        )
    except (Exception, PreviewDeadline):
        return render_template(
            "error.html", message="This opening sample could not be checked now. Please try again."
        ), 503
    try:
        measured = measurements(
            database(), current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"], report
        )
    except (Exception, PreviewDeadline):
        measured = {}
    if database().connection.execute("PRAGMA data_version").fetchone()[0] != version:
        measured = {}
    return render_template("opening_unfamiliar.html", report=report, measured=measured)
