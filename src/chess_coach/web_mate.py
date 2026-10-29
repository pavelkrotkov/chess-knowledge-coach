"""Private on-demand mate inspection page."""

from flask import Blueprint, abort, current_app, render_template, request

from .mate_auto_view import automatic_view
from .mate_inspection import inspect_mate
from .web_db import database

mate_views = Blueprint("mate", __name__)


@mate_views.get("/decisions/<int:position_id>/mate")
def detail(position_id: int):
    try:
        result = inspect_mate(
            database(),
            position_id,
            learner=current_app.config["SUBJECT"],
            expected_fingerprint=request.args.get("source"),
        )
    except ValueError:
        abort(404)
    return render_template(
        "mate_inspection.html",
        mate=result,
        automatic=automatic_view(database(), position_id, current_app.config["SUBJECT"]),
    )
