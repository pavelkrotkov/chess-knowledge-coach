"""Render the daily schedule and one optional recurring practice action."""

import sqlite3

from flask import current_app, render_template, request

from .next_focus_select import repeats_success
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
        if _room_after_due(result):
            generation = _generation(db)
            focus = current_focus(
                db,
                current_app.config["SUBJECT"],
                current_app.config["CORPUS"],
                include_optional=False,
            )
        promotion = promotion_recommendation(db, current_app.config["SUBJECT"])
    priority = bool(
        promotion
        and promotion["status"] == "ready"
        and repeats_success(focus)
        and generation is not None
        and _generation(db) == generation
    )
    return render_template(
        "plan.html",
        plan=result,
        error=None,
        focus=focus,
        promotion=promotion,
        promotion_priority=priority,
    )


def _generation(db):
    try:
        return db.connection.execute("PRAGMA data_version").fetchone()[0]
    except sqlite3.Error:
        return None


def _room_after_due(plan):
    if plan.get("scan", {}).get("due_incomplete", True):
        return False
    return sum(item["kind"] != "new" for item in plan["items"]) < 10
