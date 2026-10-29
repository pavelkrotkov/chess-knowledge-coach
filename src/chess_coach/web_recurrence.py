"""Private bounded recurring-pattern report."""

from flask import Blueprint, current_app, render_template, request

from .learner_identity import normalize_identity
from .lesson_narrative import build
from .preview_snapshot import preview_history
from .recurrence_report import default_windows, report
from .recurrence_snapshot import read_snapshot
from .web_db import database

recurrence_views = Blueprint("recurrence_views", __name__)


def _attach_lessons(result, db, subject, history):
    for period in ("previous", "current"):
        for group in result[period]:
            group["lesson"] = build(db, subject, group, _history=history)


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
        db = database()
        subject = normalize_identity(current_app.config["SUBJECT"])
        with read_snapshot(db), preview_history(db, subject) as history:
            result = report(
                db,
                subject,
                start,
                end,
                previous,
                skill=skill,
                operation=operation,
                cursor=cursor,
                _history=history,
            )
            _attach_lessons(result, db, subject, history)
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
