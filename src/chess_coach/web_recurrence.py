"""Private bounded recurring-pattern report."""

from flask import Blueprint, current_app, render_template, request

from .lesson_narrative import build
from .recurrence_report import default_windows, report
from .recurrence_snapshot import read_snapshot
from .web_db import database

recurrence_views = Blueprint("recurrence_views", __name__)


def _attach_lessons(result):
    for period in ("previous", "current"):
        for group in result[period]:
            group["lesson"] = build(database(), current_app.config["SUBJECT"], group)


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
        with read_snapshot(database()):
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
            _attach_lessons(result)
        error = None
    except ValueError:
        result, error = None, "Report unavailable; check filters and restart."
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
