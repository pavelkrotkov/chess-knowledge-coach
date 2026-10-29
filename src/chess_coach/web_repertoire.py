"""Private, attributable repertoire browser routes."""

from flask import Blueprint, abort, current_app, render_template

from .repertoire import game_detail, repertoire_report
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
