"""Render the daily schedule and one optional recurring practice action."""

from flask import current_app, render_template, request

from .next_focus_select import repeats_success
from .plan_page_focus import focus as next_focus
from .plan_page_focus import generation as current_generation
from .plan_promotion import recommendation as promotion_recommendation
from .web_db import database
from .web_protection_plan import current_focus


def render(daily_plan):
    db = database()
    try:
        result = daily_plan(
            db,
            subject=current_app.config["SUBJECT"],
            corpus_version=current_app.config["CORPUS"],
            cursor=request.args.get("cursor"),
        )
    except ValueError:
        return render_template(
            "plan.html", error="The plan changed. Restart planning.", plan=None
        ), 400
    focus = promotion = generation = None
    if not request.args.get("cursor"):
        focus, generation = next_focus(db, result, current_focus)
        promotion = promotion_recommendation(db, current_app.config["SUBJECT"])
    priority = bool(
        promotion
        and promotion["status"] == "ready"
        and repeats_success(focus)
        and generation is not None
        and current_generation(db) == generation
    )
    return render_template(
        "plan.html",
        plan=result,
        error=None,
        focus=focus,
        promotion=promotion,
        promotion_priority=priority,
    )
