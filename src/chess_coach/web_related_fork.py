"""Preview and start explicitly selected fork transfers in the private browser."""

import secrets
import sqlite3

import chess
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .related_fork import preview
from .related_fork_start import start_related
from .web_board import board_rows
from .web_db import database

related_fork = Blueprint("related_fork", __name__)


@related_fork.get("/evidence/<int:evidence_id>/related-forks")
def show(evidence_id):
    try:
        result = preview(
            database(),
            current_app.config["SUBJECT"],
            evidence_id,
            current_app.config["CORPUS"],
            request.args.get("cursor"),
        )
        for item in result["items"]:
            item["board"] = board_rows(item["fen"])
    except ValueError:
        return render_template(
            "error.html",
            message="This fork source is unsupported, unavailable, or changed. Return to the evidence.",
        ), 400
    return render_template("related_fork.html", result=result, evidence_id=evidence_id)


@related_fork.post("/evidence/<int:evidence_id>/related-forks/start")
def begin(evidence_id):
    attempt = secrets.token_urlsafe(24)
    try:
        if request.form.get("assessment") == "1":
            from .related_fork_assessment_start import start

            start(
                database(),
                attempt_id=attempt,
                subject=current_app.config["SUBJECT"],
                evidence_id=evidence_id,
                corpus_version=current_app.config["CORPUS"],
                reference=request.form.get("reference", ""),
                secret=current_app.secret_key,
                prior=request.form.get("prior") or None,
            )
        else:
            start_related(
                database(),
                attempt_id=attempt,
                subject=current_app.config["SUBJECT"],
                evidence_id=evidence_id,
                corpus_version=current_app.config["CORPUS"],
                reference=request.form.get("reference", ""),
            )
    except ValueError:
        return render_template(
            "error.html",
            message="This fork preview is unavailable or changed. Return to the evidence.",
        ), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)


@related_fork.get("/evidence/<int:evidence_id>/related-forks/find-verified")
def find_verified(evidence_id):
    from .related_fork_assessment_finder import find

    try:
        result = find(
            database(),
            current_app.config["SUBJECT"],
            evidence_id,
            current_app.config["CORPUS"],
            current_app.secret_key,
        )
        if result:
            item = result["items"][0]
            item["board"] = board_rows(item["fen"])
            item["color"] = "White" if chess.Board(item["fen"]).turn else "Black"
    except (ValueError, sqlite3.OperationalError):
        result = None
    return render_template("related_fork_assessment.html", result=result, evidence_id=evidence_id)


@related_fork.get("/plan/forks/history")
def history():
    from .fork_history import report

    try:
        result = report(database(), current_app.config["SUBJECT"], current_app.config["CORPUS"])
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return render_template("error.html", message="Fork history is unavailable or changed."), 400
    return render_template("fork_history.html", report=result)


@related_fork.get("/plan/forks/progress")
def progress():
    from .fork_progress_report import report

    try:
        result = report(database(), current_app.config["SUBJECT"], current_app.config["CORPUS"])
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return render_template(
            "error.html", message="Fork progress is unavailable or changed."
        ), 400
    return render_template("fork_progress.html", report=result)


@related_fork.get("/plan/forks/find-verified")
def find_first():
    from .fork_followup_page import page

    return page(matched=False)


@related_fork.get("/plan/forks/next")
def find_next():
    from .fork_followup_page import page

    return page(matched=True)
