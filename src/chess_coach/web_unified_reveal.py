"""Reveal a supplied continuation only through an explicit private action."""

from flask import abort, current_app, render_template, request, url_for

from .web_db import database
from .web_practice_reveal import unified_reveal


def reveal_action(current):
    attempt = current()
    if request.form.get("attempt") != attempt:
        abort(409)
    try:
        moves = unified_reveal(
            database(), attempt, current_app.config["SUBJECT"], request.form.get("event", "")
        )
    except ValueError:
        return render_template("error.html", message="The practice attempt has changed."), 400
    return render_template(
        "practice_reveal.html",
        moves=moves,
        back=url_for("unified_practice.show_page", attempt=attempt),
    )
