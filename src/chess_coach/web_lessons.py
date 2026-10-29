"""Save and inspect explicitly requested immutable lesson versions."""

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from .lesson_history import get, save
from .lesson_narrative import build
from .recurrence_report import report
from .web_db import database

lesson_views = Blueprint("lesson_views", __name__)


def _selected(data, form):
    period = form.get("period")
    if period not in {"current", "previous"}:
        return None
    for group in data[period]:
        if all(group[key] == form.get(key) for key in ("skill", "operation", "family", "version")):
            return group
    return None


@lesson_views.post("/lessons/regenerate")
def regenerate():
    db = database()
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        data = report(
            db,
            current_app.config["SUBJECT"],
            request.form["start"],
            request.form["end"],
            request.form["compare_start"],
            skill=request.form.get("filter_skill") or None,
            operation=request.form.get("filter_operation") or None,
            cursor=request.form.get("cursor") or None,
        )
        group = _selected(data, request.form)
        if group is None:
            raise ValueError("lesson unavailable")
        lesson = build(db, current_app.config["SUBJECT"], group)
        inputs = {key: data[key] for key in ("start", "end", "compare_start", "skill", "operation")}
        inputs.update(
            {key: request.form.get(key) for key in ("period", "cursor", "family", "version")}
        )
        lesson_id = save(db, current_app.config["SUBJECT"], lesson, inputs=inputs)
        db.connection.commit()
    except (ValueError, KeyError, TypeError):
        db.connection.rollback()
        abort(400, "Lesson unavailable; restart the report.")
    return redirect(url_for("lesson_views.show", lesson_id=lesson_id), code=303)


@lesson_views.get("/lessons/<int:lesson_id>")
def show(lesson_id):
    try:
        record = get(database(), current_app.config["SUBJECT"], lesson_id)
    except ValueError:
        abort(404)
    return render_template("lesson_history.html", record=record)
