"""Private direct-prompt practice without scheduling or mastery writes."""

import secrets

from flask import (
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .objective_pawn_continue import append_reply as append_pawn_reply
from .objective_promotion_continue import append_reply as append_promotion_reply
from .objective_short_history import append_reply
from .unified_session_events import show
from .unified_sessions import start
from .web_board import board_rows
from .web_db import database
from .web_practice_history import selected_step, unified_history
from .web_unified_actions import unified_practice
from .web_unified_unavailable import unavailable


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
            goal=request.form.get("goal") or None,
        )
    except ValueError:
        return render_template("error.html", message="That practice source is unavailable."), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)


@unified_practice.get("/unified/<attempt>")
def show_page(attempt):
    try:
        state = show(database(), attempt, current_app.config["SUBJECT"])
        steps = unified_history(database(), attempt, current_app.config["SUBJECT"])
        steps = append_reply(database(), attempt, current_app.config["SUBJECT"], steps)
        steps = append_pawn_reply(database(), attempt, current_app.config["SUBJECT"], steps)
        steps = append_promotion_reply(database(), attempt, current_app.config["SUBJECT"], steps)
        index = selected_step(steps, request.args.get("step"))
    except ValueError:
        return unavailable(database(), current_app.config["SUBJECT"], attempt)
    session["unified_attempt"] = attempt
    return render_template(
        "unified_practice.html",
        state=state,
        board=board_rows(steps[index]["fen"], state["learner_color"]),
        steps=steps,
        step=index,
        at_current=index == len(steps) - 1,
        board_label="Chess position; learner plays " + state["learner_color"] + " at the bottom",
        event=secrets.token_urlsafe(24),
        notice=session.pop("unified_notice", None),
    )
