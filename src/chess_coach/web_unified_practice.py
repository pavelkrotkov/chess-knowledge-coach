"""Private direct-prompt practice without scheduling or mastery writes."""

import secrets

from flask import (
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .unified_session_events import show
from .unified_sessions import start
from .web_board import board_rows
from .web_db import database
from .web_unified_actions import unified_practice


@unified_practice.post("/unified/start")
def begin():
    attempt = secrets.token_urlsafe(24)
    try:
        start(
            database(),
            attempt_id=attempt,
            subject=current_app.config["SUBJECT"],
            source_type=request.form.get("source_type", ""),
            version=request.form.get("version", ""),
            key=request.form.get("key", ""),
        )
    except ValueError:
        return render_template("error.html", message="That practice source is unavailable."), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)


@unified_practice.get("/unified/<attempt>")
def show_page(attempt):
    try:
        state = show(database(), attempt, current_app.config["SUBJECT"])
    except ValueError:
        abort(404)
    session["unified_attempt"] = attempt
    return render_template(
        "unified_practice.html",
        state=state,
        board=board_rows(state["fen"], state["learner_color"]),
        board_label="Chess position; learner plays " + state["learner_color"] + " at the bottom",
        event=secrets.token_urlsafe(24),
        notice=session.pop("unified_notice", None),
    )
