"""Private on-demand short-mate inspection of one owned game."""

from flask import Blueprint, current_app, render_template

from .short_mate_game_report import report
from .web_db import database

short_mate_game_views = Blueprint("short_mate_game_views", __name__)


@short_mate_game_views.get("/games/<int:game_id>/short-mate")
def inspect(game_id):
    try:
        result = report(database(), current_app.config["SUBJECT"], game_id)
    except (ValueError, TypeError, IndexError):
        return render_template(
            "error.html", message="This game is unavailable or changed during inspection."
        ), 400
    return render_template("short_mate_game.html", report=result)
