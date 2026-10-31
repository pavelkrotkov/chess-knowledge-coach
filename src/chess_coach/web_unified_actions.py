"""Private practice move and hint actions."""

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .unified_session_events import hint, show, submit
from .web_db import database
from .web_move_history import unified_input_fen
from .web_move_input import normalize_move
from .web_practice_messages import move_notice
from .web_unified_reveal import reveal_action

unified_practice = Blueprint("unified_practice", __name__)


def _current():
    attempt = session.get("unified_attempt")
    if not isinstance(attempt, str):
        abort(404)
    return attempt


@unified_practice.post("/unified/move")
def move():
    attempt = _current()
    if request.form.get("attempt") != attempt:
        abort(409)
    try:
        state = show(database(), attempt, current_app.config["SUBJECT"])
        event = request.form.get("event", "")
        original = unified_input_fen(
            database(), attempt, current_app.config["SUBJECT"], event, state["fen"]
        )
        move_text = normalize_move(
            original, request.form.get("move", ""), request.form.get("promotion", "")
        )
        result = submit(
            database(),
            attempt,
            current_app.config["SUBJECT"],
            event_id=event,
            move=move_text,
        )
    except ValueError:
        return render_template("error.html", message="The practice attempt has changed."), 400
    session["unified_notice"] = move_notice(result["feedback"], result.get("objective"))
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)


@unified_practice.post("/unified/hint")
def request_hint():
    attempt = _current()
    if request.form.get("attempt") != attempt:
        abort(409)
    try:
        result = hint(
            database(),
            attempt,
            current_app.config["SUBJECT"],
            event_id=request.form.get("event", ""),
        )
    except ValueError:
        return render_template("error.html", message="The practice attempt has changed."), 400
    session["unified_notice"] = "Hint: consider a piece on " + result["hint"]
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)


@unified_practice.post("/unified/reveal")
def reveal():
    return reveal_action(_current)
