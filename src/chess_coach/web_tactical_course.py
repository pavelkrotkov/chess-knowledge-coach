"""Display one offered private tactical export without rebuilding it."""

from pathlib import Path
from types import SimpleNamespace

from flask import Blueprint, abort, current_app, render_template, request

from .tactical_course_display import chapter as display
from .tactical_course_offer_read import offered
from .tactical_study_request_status import status
from .web_tactical_study import submit

tactical_course_views = Blueprint("tactical_course_views", __name__)


def _index(name, count):
    value = request.args.get(name, "0")
    if not value.isascii() or not value.isdecimal() or len(value) > 4:
        abort(400)
    index = int(value)
    if index >= count:
        abort(400)
    return index


@tactical_course_views.get("/coaching/tactical-course")
def show():
    try:
        item, course = offered(
            current_app.config["PROJECT_ROOT"],
            current_app.config["DB_PATH"],
            current_app.config["SUBJECT"],
            current_app.config["CORPUS"],
        )
        expected = request.args.get("version")
        if expected is not None and expected != item["hash"]:
            abort(409, "The offered course changed. Return to Coaching.")
        index = _index("chapter", len(course["chapters"]))
        lines = course["chapters"][index]["source_snapshot"]["lines"]
        shown = display(course["chapters"][index], index, _index("line", len(lines)))
        source = shown["chapter"]["source"]
        shown["evidence"] = source.get("evidence_id") or source.get("binding", {}).get(
            "evidence_id"
        )
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return render_template("tactical_course_browser.html", course=None), 200
    db = SimpleNamespace(path=Path(current_app.config["DB_PATH"]))
    study = status(
        db,
        current_app.config["PROJECT_ROOT"],
        current_app.config["SUBJECT"],
        current_app.config["CORPUS"],
        item,
        course,
    )
    return render_template(
        "tactical_course_browser.html", course=course, offer=item, shown=shown, study=study
    )


tactical_course_views.add_url_rule(
    "/coaching/tactical-course/study", view_func=submit, methods=["POST"]
)
