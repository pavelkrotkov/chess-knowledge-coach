"""Start a signed legacy plan offer without partial training writes."""

import secrets

from flask import current_app, redirect, render_template, session, url_for


def start(db, version, puzzle_id, offer):
    from .curriculum_window_legacy import start as start_window

    attempt = secrets.token_urlsafe(24)
    try:
        item_id, _ = start_window(
            db, current_app.config["SUBJECT"], version, puzzle_id, attempt, offer
        )
    except ValueError:
        return render_template(
            "error.html", message="The practice window expired or the plan changed."
        ), 400
    session["attempt"] = attempt
    session["item_id"] = item_id
    return redirect(url_for("practice.show"), code=303)
