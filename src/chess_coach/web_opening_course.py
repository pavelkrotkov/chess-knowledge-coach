"""Render and export a version-bound, read-only opening course preview."""

import sqlite3

from flask import Response, abort, current_app, render_template, request, url_for

from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import DeadlineConflict, PreviewDeadline
from .web_board import board_rows
from .web_db import database
from .web_opening_course_select import preview
from .web_tactical_exposure import record


def _study(course, game_id, position_id, move):
    from .opening_study_course import build
    from .opening_study_view import status

    selection = {"game_id": game_id, "position_id": position_id, "move": move}
    try:
        body = build(course, course["version"], game_id, position_id, move)
        return status(
            database(),
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            course,
            revision=body,
            selection=selection,
        )
    except (ValueError, TypeError, KeyError):
        return None


def show(game_id, position_id, move):
    try:
        course = preview(
            database(),
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            game_id,
            position_id,
            move,
            request.args.get("recommendation"),
        )
    except (PreviewDeadline, PreviewUnavailable, DeadlineConflict, sqlite3.Error, OSError):
        abort(503, "The course preview could not be checked now. Please try again.")
    except ValueError:
        abort(404)
    except RuntimeError as error:
        if str(error) != "deep engine is unavailable":
            raise
        abort(503, "The course preview could not be checked now. Please try again.")
    if request.args.get("download") == "1":
        if request.args.get("version") != course["version"]:
            abort(409)
        document = "\n\n".join(chapter["pgn"] for chapter in course["chapters"]) + "\n"
        response = Response(
            document,
            mimetype="application/x-chess-pgn",
            headers={
                "Content-Disposition": 'attachment; filename="opening-revision-course.pgn"',
                "Cache-Control": "private, no-store",
            },
        )
        record(course["version"], list(enumerate(course["chapters"])), "download")
        return response
    download = url_for(
        "opening_experiments.course",
        game_id=game_id,
        position_id=position_id,
        move=move,
        download=1,
        version=course["version"],
        recommendation=request.args.get("recommendation"),
    )
    study = _study(course, game_id, position_id, move)
    page = render_template(
        "opening_revision_course.html",
        course=course,
        exposure_unavailable=database().compat32,
        study=study,
        download_url=download,
        board=board_rows(course["decision"]["fen"], course["decision"]["color"]),
    )

    record(course["version"], list(enumerate(course["chapters"])), "served")
    return page
