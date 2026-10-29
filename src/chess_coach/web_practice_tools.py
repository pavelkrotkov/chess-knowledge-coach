"""Explicit hint and reveal actions for existing training attempts."""

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from .puzzle_session_events import request_hint as puzzle_hint
from .training_feedback import show_training_puzzle
from .web_db import current_training, database, form_matches
from .web_practice_reveal import puzzle_reveal

practice_tools = Blueprint("practice_tools", __name__)


def _current():
    attempt, item_id = current_training()
    if not form_matches(attempt, item_id):
        abort(409)
    show_training_puzzle(database(), attempt, item_id=item_id)
    return attempt


@practice_tools.post("/practice/hint")
def hint():
    try:
        result = puzzle_hint(database(), _current(), event_id=request.form.get("event", ""))
        square = result["hint"]
        if not isinstance(square, str):
            raise ValueError("hint unavailable")
    except ValueError:
        return render_template("error.html", message="The practice attempt has changed."), 400
    session["notice"] = "Hint: consider a piece on " + square
    return redirect(url_for("practice.show"), code=303)


@practice_tools.post("/practice/reveal")
def reveal():
    try:
        moves = puzzle_reveal(database(), _current(), request.form.get("event", ""))
    except ValueError:
        return render_template("error.html", message="The practice attempt has changed."), 400
    return render_template("practice_reveal.html", moves=moves, back=url_for("practice.show"))
