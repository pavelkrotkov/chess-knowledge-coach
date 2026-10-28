"""Start and complete verified training sessions through domain services."""

import secrets

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

from .puzzle_sessions import start_attempt
from .training import create_training_item
from .training_feedback import puzzle_training_ref, show_training_puzzle, submit_training_move
from .web_board import board_rows
from .web_completion import completion
from .web_db import current_training, database
from .web_recommendation import recommended

practice = Blueprint("practice", __name__)


@practice.post("/practice/start")
def start():
    db = database()
    version = request.form.get("version", "")
    puzzle_id = request.form.get("puzzle_id", "")
    ref = puzzle_training_ref(version, puzzle_id)
    if not recommended(db, version, puzzle_id, request.form.get("cursor") or None):
        return render_template(
            "error.html",
            message="The plan changed. Return to the daily plan and choose an available item.",
        ), 400
    item_id = create_training_item(
        db, source_type="puzzle", source_ref=ref, skill="mate_in_one", operation="execute"
    )
    attempt = secrets.token_urlsafe(24)
    start_attempt(db, attempt_id=attempt, version=version, puzzle_id=puzzle_id)
    session["attempt"] = attempt
    session["item_id"] = item_id
    return redirect(url_for("practice.show"), code=303)


@practice.get("/practice")
def show():
    attempt, item_id = current_training()
    try:
        state = show_training_puzzle(database(), attempt, item_id=item_id)
    except ValueError:
        abort(404)
    feedback = completion(database(), attempt, item_id)
    return render_template(
        "practice.html",
        state=state,
        board=board_rows(state["fen"]),
        completion=feedback,
        notice=session.pop("notice", None),
        event=secrets.token_urlsafe(24),
    )


@practice.post("/practice/move")
def move():
    attempt, item_id = current_training()
    try:
        result = submit_training_move(
            database(),
            attempt,
            event_id=request.form.get("event", ""),
            move=request.form.get("move", "").strip(),
            item_id=item_id,
            subject=current_app.config["SUBJECT"],
        )
    except ValueError:
        return render_template(
            "error.html",
            message="That move is not legal or the attempt has changed. Return to practice and try again.",
        ), 400
    if result.get("feedback") == "illegal":
        session["notice"] = "That move is not legal. Try again."
    return redirect(url_for("practice.show"), code=303)
