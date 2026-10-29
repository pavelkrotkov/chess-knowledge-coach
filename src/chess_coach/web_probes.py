"""Offer private, source-bound diagnostic tasks from saved lessons."""

import secrets

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from .probe_events import event
from .probe_sessions import start
from .probe_views import show
from .web_board import board_rows
from .web_db import database

probe_views = Blueprint("probe_views", __name__)


@probe_views.post("/probes/start")
def begin():
    try:
        state = start(
            database(),
            current_app.config["SUBJECT"],
            request.form["attempt"],
            int(request.form["lesson"]),
            int(request.form["evidence"]),
            request.form["kind"],
        )
    except (ValueError, KeyError, TypeError):
        abort(400, "This probe is unavailable or its lesson source has changed.")
    return redirect(url_for("probe_views.page", attempt=state["attempt_id"]), code=303)


@probe_views.get("/probes/<attempt>")
def page(attempt):
    try:
        state = show(database(), current_app.config["SUBJECT"], attempt)
    except ValueError:
        abort(404)
    return render_template(
        "probe.html", state=state, board=board_rows(state["fen"]), event=secrets.token_urlsafe(24)
    )


@probe_views.post("/probes/<attempt>/event")
def submit(attempt):
    kind = request.form.get("kind", "")
    try:
        event(
            database(),
            current_app.config["SUBJECT"],
            attempt,
            request.form.get("event", ""),
            kind,
            request.form.get("answer") if kind == "answer" else None,
        )
    except ValueError:
        abort(400, "This probe or response is unavailable.")
    return redirect(url_for("probe_views.page", attempt=attempt), code=303)


@probe_views.app_context_processor
def probe_context():
    return {"probe_attempt": secrets.token_urlsafe(24)}


@probe_views.get("/lessons/<int:lesson_id>/probes")
def history(lesson_id):
    from .lesson_history import get

    db = database()
    subject = current_app.config["SUBJECT"]
    try:
        get(db, subject, lesson_id)
    except ValueError:
        abort(404)
    rows = db.connection.execute(
        """SELECT attempt_id, started_at FROM diagnostic_probes
           WHERE subject=? AND lesson_id=? ORDER BY started_at DESC, attempt_id LIMIT 100""",
        (subject, lesson_id),
    ).fetchall()
    return render_template("probe_history.html", lesson_id=lesson_id, rows=rows)
