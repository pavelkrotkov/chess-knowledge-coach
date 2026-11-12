"""Queue an exact private opening Study from an authenticated form."""

from flask import abort, current_app, redirect, request, url_for

from .opening_study_request import enqueue
from .tactical_course_deadline import PreviewDeadline
from .web_db import database


def submit():
    selection = {key: request.form.get(key, "") for key in ("color", "parent", "move")}
    version = request.form.get("version", "")
    try:
        enqueue(
            database(),
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            version,
            selection,
        )
    except (Exception, PreviewDeadline):
        abort(409, "This Study request cannot be checked now. Open a new preview.")
    return redirect(
        url_for(
            "repertoire_views.unfamiliar_course",
            color=selection["color"],
            parent=selection["parent"],
            move=selection["move"],
        )
    )


def selection():
    values = {key: request.args.get(key) for key in ("color", "parent", "move")}
    if not any(values.values()):
        return None
    if not all(values.values()):
        abort(400, "The opening selection is incomplete.")
    return values
