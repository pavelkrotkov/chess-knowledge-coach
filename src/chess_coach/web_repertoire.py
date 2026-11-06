"""Private, attributable repertoire browser routes."""

from flask import Blueprint, abort, current_app, render_template

from .opening_decision import inspect
from .repertoire import game_detail, repertoire_report
from .web_board import board_rows
from .web_db import database

repertoire_views = Blueprint("repertoire_views", __name__)


@repertoire_views.get("/repertoire")
def repertoire():
    try:
        report = repertoire_report(database(), current_app.config["SUBJECT"])
    except ValueError:
        report = None
    return render_template("repertoire.html", report=report)


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
        result = inspect(database(), game_id, position_id, current_app.config["SUBJECT"])
    except ValueError:
        return render_template(
            "error.html",
            message="This opening decision is unavailable. Its ownership, game history, or pinned classification may be missing or changed.",
        ), 404
    return render_template(
        "opening_decision.html", decision=result, board=board_rows(result["fen"], result["color"])
    )
