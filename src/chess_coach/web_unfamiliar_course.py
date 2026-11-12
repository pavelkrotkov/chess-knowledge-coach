"""Render or download a version-checked private opening course."""

from flask import Response, abort, current_app, render_template, request, url_for

from .opening_study_view import status
from .opening_unfamiliar_course import preview
from .tactical_course_deadline import PreviewDeadline
from .web_board import board_rows
from .web_db import database
from .web_opening_study import selection as _selection


def _load(selection):
    try:
        args = (database(), current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"])
        return preview(*args, selection) if selection else preview(*args)
    except ValueError:
        if selection:
            abort(409, "The opening selection or its source changed. Open a new preview.")
        abort(503, "The opening course could not be checked now. Please try again.")
    except (Exception, PreviewDeadline):
        abort(503, "The opening course could not be checked now. Please try again.")


def show():
    selection = _selection()
    course = _load(selection)
    if request.args.get("download") == "1":
        if request.args.get("version") != course["version"]:
            abort(409, "The opening course changed. Open a new preview.")
        if not course["chapters"]:
            abort(404)
        document = "\n\n".join(item["pgn"] for item in course["chapters"]) + "\n"
        return Response(
            document,
            mimetype="application/x-chess-pgn",
            headers={
                "Content-Disposition": 'attachment; filename="unfamiliar-opening-course.pgn"',
                "Cache-Control": "private, no-store",
            },
        )
    study = (
        status(
            database(), current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"], course
        )
        if selection
        else None
    )
    for item in course["chapters"]:
        item["board"] = board_rows(item["fen"], item["color"])
    download = url_for(
        "repertoire_views.unfamiliar_course",
        download=1,
        version=course["version"],
        **(selection or {}),
    )
    return render_template(
        "opening_unfamiliar_course.html",
        course=course,
        download_url=download,
        study=study,
    )
