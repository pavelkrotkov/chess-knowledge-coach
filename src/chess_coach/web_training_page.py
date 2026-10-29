"""Render an existing training attempt and its played move history."""

import secrets

from flask import abort, render_template, request, session

from .training_feedback import show_training_puzzle
from .web_board import board_rows
from .web_completion import completion
from .web_db import current_training, database
from .web_practice_history import puzzle_history, selected_step


def render_training_page():
    attempt, item_id = current_training()
    try:
        state = show_training_puzzle(database(), attempt, item_id=item_id)
        steps, color = puzzle_history(database(), attempt)
        index = selected_step(steps, request.args.get("step"))
    except ValueError:
        abort(404)
    feedback = completion(database(), attempt, item_id)
    return render_template(
        "practice.html",
        state=state,
        item_id=item_id,
        board=board_rows(steps[index]["fen"], color),
        board_label="Chess position; learner plays " + color + " at the bottom",
        steps=steps,
        step=index,
        at_current=index == len(steps) - 1,
        completion=feedback,
        notice=session.pop("notice", None),
        event=secrets.token_urlsafe(24),
    )
