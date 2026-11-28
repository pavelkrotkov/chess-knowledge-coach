"""Render the daily schedule and one optional recurring practice action."""

import sqlite3

from flask import current_app, render_template, request

from .opening_context_launch_input import before as selected_context
from .opening_context_launch_page import attach as attach_context
from .plan_page_focus import focus as next_focus
from .plan_page_options import minutes, priority, validate_advisory
from .plan_promotion import recommendation as promotion_recommendation
from .renewal_diagnostics import refusal
from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline
from .web_db import database
from .web_protection_plan import current_focus


def render(daily_plan):
    db = database()
    try:
        current = selected_context(
            db,
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            request.args.get("opening"),
            request.args.get("opening_token"),
            request.args.get("cursor"),
        )
        result = daily_plan(
            db,
            subject=current_app.config["SUBJECT"],
            corpus_version=current_app.config["CORPUS"],
            limit=int(request.args.get("limit", "10")),
            cursor=request.args.get("cursor"),
            goal=request.args.get("goal") or None,
            duration_minutes=minutes(request.args.get("minutes")),
            renew=request.args.get("renew") == "1",
            project_root=current_app.config["PROJECT_ROOT"],
        )
        if current is not None:
            attach_context(
                db,
                current_app.config["PROJECT_ROOT"],
                current_app.config["SUBJECT"],
                current_app.config["CORPUS"],
                current,
                result,
            )
    except (ValueError, OSError, sqlite3.Error, PreviewUnavailable, PreviewDeadline) as error:
        if request.args.get("renew") == "1":
            refusal("request", error)
            message = "The plan could not be renewed. Retry renewal or choose a fresh plan."
        else:
            message = (
                "The plan changed or the chosen goal or window is unavailable. Restart planning."
            )
        return render_template("plan.html", error=message, plan=None), 400
    validate_advisory(db, result)
    focus = promotion = generation = None
    if not request.args.get("cursor") and "window" not in result:
        focus, generation = next_focus(db, result, current_focus)
        promotion = promotion_recommendation(db, current_app.config["SUBJECT"])
    promotion_first = priority(db, promotion, focus, generation)
    return render_template(
        "plan.html",
        plan=result,
        error=None,
        focus=focus,
        promotion=promotion,
        promotion_priority=promotion_first,
    )
