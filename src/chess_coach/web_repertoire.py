"""Private, attributable repertoire browser routes."""

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from .opening_decision import inspect
from .opening_experiment import qualified as qualifies_experiment
from .opening_explore import explore
from .opening_explore_enrich import enrich
from .opening_queue_request import admit
from .opening_queue_view import statuses
from .opening_reference_read import matches
from .repertoire import game_detail, repertoire_report
from .tactical_course_deadline import PreviewDeadline
from .web_board import board_rows
from .web_db import database
from .web_opening_study import submit as submit_unfamiliar_study
from .web_unfamiliar_course import show as show_unfamiliar_course
from .web_unfamiliar_measure import show as show_unfamiliar

repertoire_views = Blueprint("repertoire_views", __name__)


@repertoire_views.get("/repertoire")
def repertoire():
    try:
        report = repertoire_report(database(), current_app.config["SUBJECT"])
    except ValueError:
        report = None
    return render_template("repertoire.html", report=report)


@repertoire_views.get("/repertoire/explore")
def opening_explore():
    try:
        report = explore(database(), current_app.config["SUBJECT"])
        enrich(
            database(), current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"], report
        )
    except (Exception, PreviewDeadline):
        return render_template(
            "error.html", message="This opening sample could not be checked now. Please try again."
        ), 503
    return render_template("opening_explore.html", report=report)


@repertoire_views.get("/repertoire/unfamiliar")
def opening_unfamiliar():
    return show_unfamiliar()


@repertoire_views.get("/repertoire/unfamiliar/course")
def unfamiliar_course():
    return show_unfamiliar_course()


@repertoire_views.post("/repertoire/unfamiliar/course/study")
def unfamiliar_study():
    return submit_unfamiliar_study()


@repertoire_views.get("/repertoire/games/<int:game_id>")
def repertoire_game(game_id: int):
    try:
        game = game_detail(database(), current_app.config["SUBJECT"], game_id)
    except ValueError:
        abort(404)
    return render_template("repertoire_game.html", game=game)


@repertoire_views.get("/repertoire/games/<int:game_id>/openings/<int:position_id>")
def opening_decision(game_id: int, position_id: int):
    try:
        result = inspect(
            database(),
            game_id,
            position_id,
            current_app.config["SUBJECT"],
            alternative=request.args.get("alternative"),
        )
    except ValueError:
        return render_template(
            "error.html",
            message="This opening decision is unavailable. Its ownership, game history, or pinned classification may be missing or changed.",
        ), 404
    try:
        comparisons = statuses(
            database(), current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"], result
        )
    except (Exception, PreviewDeadline):
        comparisons = {}
    return render_template(
        "opening_decision.html",
        decision=result,
        comparisons=comparisons,
        qualifies_experiment=qualifies_experiment,
        board=board_rows(result["fen"], result["color"]),
    )


@repertoire_views.post("/repertoire/games/<int:game_id>/openings/<int:position_id>/compare")
def opening_compare(game_id: int, position_id: int):
    try:
        admit(
            database(),
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            game_id,
            position_id,
            request.form.get("alternative", ""),
            retry=request.form.get("retry") == "1",
        )
    except (Exception, PreviewDeadline):
        return render_template(
            "error.html",
            message="This comparison cannot be queued now. Another request may be pending, or this source may have changed.",
        ), 409
    return redirect(
        url_for(
            "repertoire_views.opening_decision",
            game_id=game_id,
            position_id=position_id,
            alternative=request.form.get("alternative", ""),
        )
    )


@repertoire_views.get("/repertoire/games/<int:game_id>/openings/<int:position_id>/references")
def opening_references(game_id: int, position_id: int):
    try:
        decision = inspect(database(), game_id, position_id, current_app.config["SUBJECT"])
    except ValueError:
        abort(404)
    references = matches(
        current_app.config["PROJECT_ROOT"],
        current_app.config["SUBJECT"],
        decision["catalog"]["parent"],
    )
    return render_template("opening_references.html", decision=decision, references=references)
