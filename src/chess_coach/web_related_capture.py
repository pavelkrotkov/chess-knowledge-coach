"""Preview and start current owned capture transfers in the private browser."""

import secrets
import sqlite3

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .related_capture import preview
from .related_capture_start import start_related
from .web_board import board_rows
from .web_db import database

related_capture = Blueprint("related_capture", __name__)


@related_capture.get("/decisions/<int:position>/related-captures")
def show(position):
    try:
        result = preview(
            database(),
            current_app.config["SUBJECT"],
            position,
            current_app.config["CORPUS"],
            request.args.get("cursor"),
            secret=current_app.secret_key,
        )
        for item in result["items"]:
            item["board"] = board_rows(item["fen"])
    except ValueError:
        return render_template(
            "error.html",
            message="No current supported capture observation, or the preview changed. Restart from the decision.",
        ), 400
    return render_template("related_capture.html", result=result, position=position)


@related_capture.post("/decisions/<int:position>/related-captures/start")
def begin(position):
    subject = current_app.config["SUBJECT"]
    corpus = current_app.config["CORPUS"]
    reference = request.form.get("reference", "")
    attempt = secrets.token_urlsafe(24)
    try:
        start_related(
            database(),
            attempt_id=attempt,
            subject=subject,
            position=position,
            corpus_version=corpus,
            reference=reference,
            assessment=request.form.get("assessment") == "1",
            secret=current_app.secret_key,
        )
    except ValueError:
        return render_template(
            "error.html",
            message="This example changed or the capture could not be verified. Try another example or practice the supplied line.",
        ), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)


@related_capture.get("/plan/captures")
def plan():
    from .capture_plan import report

    try:
        result = report(database(), current_app.config["SUBJECT"])
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return render_template("capture_plan.html", report=None, error=True)
    return render_template("capture_plan.html", report=result, error=None)
