"""Browse saved historical lesson versions."""

from flask import Blueprint, abort, current_app, render_template, request

from .lesson_history import list_versions
from .web_db import database

lesson_history_views = Blueprint("lesson_history_views", __name__)


@lesson_history_views.get("/lessons")
def history():
    try:
        before = int(request.args.get("before", str(2**63 - 1)))
        items, next_before = list_versions(database(), current_app.config["SUBJECT"], before)
    except (ValueError, TypeError):
        abort(400)
    return render_template("lessons.html", items=items, next_before=next_before)
