"""Private bounded recurring-pattern report."""

from flask import Blueprint, current_app, render_template, request

from .recurrence_report import default_windows, report
from .web_db import database

recurrence_views = Blueprint("recurrence_views", __name__)


@recurrence_views.get("/recurrence")
def recurrence():
    defaults = default_windows()
    start = request.args.get("start") or defaults[0]
    end = request.args.get("end") or defaults[1]
    previous = request.args.get("compare_start") or defaults[2]
    skill = request.args.get("skill") or None
    operation = request.args.get("operation") or None
    cursor = request.args.get("cursor") or None
    try:
        result = report(
            database(),
            current_app.config["SUBJECT"],
            start,
            end,
            previous,
            skill=skill,
            operation=operation,
            cursor=cursor,
        )
        error = None
    except ValueError as exc:
        result, error = None, str(exc)
    return render_template(
        "recurrence.html",
        report=result,
        error=error,
        start=start,
        end=end,
        previous=previous,
        skill=skill,
        operation=operation,
    )
