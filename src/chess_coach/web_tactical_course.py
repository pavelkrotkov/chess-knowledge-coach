"""Display one offered private tactical export without rebuilding it."""

from pathlib import Path
from types import SimpleNamespace

from flask import Blueprint, Response, abort, current_app, render_template, request

from .course_parts import from_course
from .tactical_course_display import chapter as display
from .tactical_course_offer_read import offered
from .tactical_course_presentation import lines as presentation_lines
from .tactical_course_selection import CURRENT_PAIRS
from .tactical_study_request_status import status
from .web_db import database
from .web_tactical_exposure import record as _record
from .web_tactical_prepare import preparation, preparation_details, prepare
from .web_tactical_study import submit

tactical_course_views = Blueprint("tactical_course_views", __name__)


def _index(name, count, default=0):
    value = request.args.get(name, str(default))
    if not value.isascii() or not value.isdecimal() or len(value) > 4:
        abort(400)
    index = int(value)
    if index >= count:
        abort(400)
    return index


@tactical_course_views.get("/coaching/tactical-course")
def show():
    """Read the prepared offer and request status without running preparation."""
    try:
        item, course = offered(
            current_app.config["PROJECT_ROOT"],
            current_app.config["DB_PATH"],
            current_app.config["SUBJECT"],
            current_app.config["CORPUS"],
        )
        manifest = from_course(course, item["hash"])
        part_index = _index("part", manifest["part_count"])
        part = manifest["parts"][part_index]
        expected = request.args.get("version")
        if request.args.get("download") == "1":
            if expected != item["hash"]:
                abort(409, "The offered course changed. Return to Coaching.")
            return _download(part, item["hash"])
        if expected is not None and expected != item["hash"]:
            abort(409, "The offered course changed. Return to Coaching.")
        index = _index("chapter", len(course["chapters"]), part["indices"][0])
        if index not in part["indices"]:
            abort(400, "Chapter is outside the selected part.")
        lines = presentation_lines(course["chapters"][index])
        shown = display(course["chapters"][index], index, _index("line", len(lines)))
        source = shown["chapter"]["source"]
        shown["evidence"] = source.get("evidence_id") or source.get("binding", {}).get(
            "evidence_id"
        )
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        if request.args.get("download") == "1":
            abort(404, "No valid offered course is available.")
        return render_template(
            "tactical_course_browser.html",
            course=None,
            preparation=preparation(),
            preparation_details=preparation_details(),
            choices=CURRENT_PAIRS,
        ), 200
    db = SimpleNamespace(path=Path(current_app.config["DB_PATH"]))
    study = status(
        db,
        current_app.config["PROJECT_ROOT"],
        current_app.config["SUBJECT"],
        current_app.config["CORPUS"],
        item,
        course,
    )
    # Only a validated current offer can confirm completion after interruption.
    page = render_template(
        "tactical_course_browser.html",
        course=course,
        manifest=manifest,
        part=part,
        offer=item,
        shown=shown,
        study=study,
        preparation=preparation(item),
        preparation_details=preparation_details(),
        choices=CURRENT_PAIRS,
        exposure_unavailable=database().compat32,
    )
    _record(item["hash"], [(index, course["chapters"][index])], "served", line=shown["line"])
    return page


def _download(part, artifact):
    name = (
        "tactical-course.pgn"
        if part["count"] == 1
        else f"tactical-course-part-{part['number']}.pgn"
    )
    response = Response(
        part["pgn"],
        mimetype="application/x-chess-pgn",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
        },
    )
    _record(artifact, list(zip(part["indices"], part["chapters"], strict=True)), "download")
    return response


tactical_course_views.add_url_rule(
    "/coaching/tactical-course/study", view_func=submit, methods=["POST"]
)


tactical_course_views.add_url_rule(
    "/coaching/tactical-course/prepare", view_func=prepare, methods=["POST"]
)
