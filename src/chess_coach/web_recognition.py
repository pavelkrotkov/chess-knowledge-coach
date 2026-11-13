"""Private, neutral recognition checks with explicit first answers."""

import secrets

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from .recognition_messages import unavailable
from .recognition_response import respond
from .recognition_store import recent, start
from .recognition_view import view
from .web_board import board_rows
from .web_db import database

recognition_views = Blueprint("recognition_views", __name__)


@recognition_views.get("/recognition")
def index():
    attempts = recent(database(), current_app.config["SUBJECT"])
    return render_template("recognition_index.html", attempts=attempts)


@recognition_views.post("/recognition/start")
def begin():
    attempt = secrets.token_urlsafe(24)
    try:
        start(database(), current_app.config["SUBJECT"], current_app.config["CORPUS"], attempt)
    except ValueError as error:
        return render_template(
            "recognition_index.html",
            attempts=recent(database(), current_app.config["SUBJECT"]),
            notice=unavailable(error),
        )
    return redirect(url_for("recognition_views.show", attempt=attempt), code=303)


@recognition_views.get("/recognition/<attempt>")
def show(attempt):
    try:
        state = view(database(), current_app.config["SUBJECT"], attempt)
    except ValueError:
        return render_template("error.html", message="That check is unavailable."), 404
    return render_template(
        "recognition.html",
        state=state,
        attempt=attempt,
        board=board_rows(state.get("fen"), state.get("color")),
    )


@recognition_views.post("/recognition/<attempt>/answer")
def answer(attempt):
    action = request.form.get("action", "")
    choice = request.form.get("choice") if action == "answer" else None
    try:
        respond(database(), current_app.config["SUBJECT"], attempt, action, choice)
    except ValueError as error:
        return render_template("error.html", message=unavailable(error)), 400
    return redirect(url_for("recognition_views.show", attempt=attempt), code=303)
