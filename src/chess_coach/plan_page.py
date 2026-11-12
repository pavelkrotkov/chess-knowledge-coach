"""Render the daily schedule and one optional recurring practice action."""

from flask import current_app, render_template, request

from .plan_promotion import recommendation as promotion_recommendation
from .web_db import database
from .web_protection_plan import current_focus


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
    focus = promotion = None
    if not request.args.get("cursor"):
        if _room_after_due(result):
            focus = current_focus(
                database(), current_app.config["SUBJECT"], current_app.config["CORPUS"]
            )
        promotion = promotion_recommendation(database(), current_app.config["SUBJECT"])
    return render_template("plan.html", plan=result, error=None, focus=focus, promotion=promotion)


def _room_after_due(plan):
    if plan.get("scan", {}).get("due_incomplete", True):
        return False
    return sum(item["kind"] != "new" for item in plan["items"]) < 10
