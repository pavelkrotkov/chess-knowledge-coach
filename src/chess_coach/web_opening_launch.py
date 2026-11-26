"""Carry an optional selected opening into the existing unified start."""

from flask import current_app, render_template, request


def options():
    return {
        "opening_token": request.form.get("opening_token") or None,
        "opening_window_cursor": request.form.get("opening_window_cursor") or None,
        "project_root": current_app.config["PROJECT_ROOT"],
        "plan_cursor": request.form.get("cursor") or None,
        "plan_corpus": current_app.config["CORPUS"],
    }


def start_error():
    message = "That practice source is unavailable."
    if request.form.get("window_offer"):
        message = "That offer changed or expired. Return to the plan and renew to recheck unstarted offers."
    return render_template("error.html", message=message), 400
