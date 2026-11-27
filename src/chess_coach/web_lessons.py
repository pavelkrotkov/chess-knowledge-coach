"""Save and inspect explicitly requested immutable lesson versions."""

from flask import Blueprint, abort, current_app, redirect, request, url_for

from .lesson_generator import generate
from .lesson_history import get, save
from .recurrence_snapshot import read_snapshot
from .web_db import database
from .web_lesson_helpers import display, draft

lesson_views = Blueprint("lesson_views", __name__)


@lesson_views.post("/lessons/regenerate")
def regenerate():
    db = database()
    try:
        subject = current_app.config["SUBJECT"]
        with read_snapshot(db):
            data, canonical = draft(db, subject, request.form)
        generator, model = current_app.extensions.get("lesson_generator", (None, None))
        lesson, provenance = generate(db, canonical, generator, model=model)
        if db.connection.in_transaction:
            raise ValueError("lesson generator left an active transaction")
        db.connection.execute("BEGIN IMMEDIATE")
        current, checked = draft(db, subject, request.form)
        if (current, checked) != (data, canonical):
            raise ValueError("lesson source changed")
        inputs = {key: data[key] for key in ("start", "end", "compare_start", "skill", "operation")}
        inputs.update(
            {key: request.form.get(key) for key in ("period", "cursor", "family", "version")}
        )
        inputs["generation"] = provenance
        lesson_id = save(
            db,
            subject,
            lesson,
            model=model if provenance["status"] == "validated" else "deterministic",
            prompt_version=provenance["prompt_version"] if generator else canonical["version"],
            inputs=inputs,
        )
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
    return display(record, database(), current_app.config["SUBJECT"])
