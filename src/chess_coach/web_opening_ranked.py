"""Render and download one source-current ranked opening course."""

from flask import Response, abort, current_app, render_template, request, url_for

from .opening_context_launch_guard import validate
from .opening_unfamiliar_course import preview
from .tactical_course_deadline import PreviewDeadline
from .web_board import board_rows
from .web_db import database


def show():
    db = database()
    root, subject = current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"]
    choice = request.args.get("choice", "")
    teaching = request.args.get("teaching") == "1"
    try:
        course, context = preview(
            db, root, subject, choice=choice, with_context=True, teaching=teaching
        )
        download = url_for(
            "repertoire_views.opening_unfamiliar",
            ranked=1,
            choice=choice,
            download=1,
            version=course["version"],
            teaching="1" if teaching else None,
        )
        if request.args.get("download") == "1":
            if request.args.get("version") != course["version"]:
                raise ValueError("opening course changed")
            response = Response(
                "\n\n".join(chapter["pgn"] for chapter in course["chapters"]) + "\n",
                mimetype="application/x-chess-pgn",
                headers={"Cache-Control": "private, no-store"},
            )
        else:
            selection, snapshot = course["selection"], course["chapters"][0]["source_snapshot"]
            study = _study(db, root, subject, choice, course, context, teaching)
            response = render_template(
                "opening_ranked_course.html",
                course=course,
                study=study,
                download_url=download,
                teaching=teaching,
                board=board_rows(snapshot["prompt_fen"], selection["color"]),
            )
        validate(context, db, root, subject)
        return response
    except ValueError:
        abort(
            409, "The ranked opening course could not be verified as current. Open a new preview."
        )
    except (Exception, PreviewDeadline):
        abort(503, "The ranked opening course could not be checked now.")


def _study(db, root, subject, choice, course, context, teaching):
    from .opening_ranked_study_course import build
    from .opening_study_view import status

    if teaching:
        if course["public_status"] != "available":
            return None
        from .opening_ranked_teaching_study import build as teaching_study

        revision = teaching_study(
            course, course["version"], context, context["teaching_qualification"]
        )
    else:
        revision = build(course, course["version"], context)
    return status(
        db, root, subject, course, revision=revision, selection={"context_choice": choice}
    )
