"""Render the daily schedule and its optional advisory capture next step."""

from flask import current_app, render_template, request

from .plan_capture_action import recommendation
from .web_db import database


def render(daily_plan):
    try:
        result = daily_plan(
            database(),
            subject=current_app.config["SUBJECT"],
            corpus_version=current_app.config["CORPUS"],
            cursor=request.args.get("cursor"),
        )
    except ValueError:
        return render_template(
            "plan.html", error="The plan changed. Restart planning.", plan=None
        ), 400
    capture = None
    if not request.args.get("cursor"):
        capture = recommendation(
            database(), current_app.config["SUBJECT"], current_app.config["CORPUS"]
        )
    return render_template("plan.html", plan=result, error=None, capture=capture)
