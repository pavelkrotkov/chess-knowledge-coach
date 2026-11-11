"""Private on-demand short-mate inspection of one owned game."""

from flask import Blueprint, current_app, render_template

from .capture_game_report import report as capture_report
from .capture_game_trend_report import report as capture_trend_report
from .fork_game_trend_report import report as fork_trend_report
from .learner_identity import normalize_identity
from .short_mate_game_report import report
from .short_mate_trend_report import report as trend_report
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


@short_mate_game_views.get("/game-samples/short-mate")
def samples():
    subject = normalize_identity(current_app.config["SUBJECT"])
    if subject is None:
        return render_template("error.html", message="Learner identity is unavailable."), 400
    result = trend_report(database(), subject, current_app.config["PROJECT_ROOT"])
    return render_template("short_mate_trend.html", report=result)


@short_mate_game_views.get("/games/<int:game_id>/capture-opportunities")
def captures(game_id):
    try:
        result = capture_report(database(), current_app.config["SUBJECT"], game_id)
    except (ValueError, TypeError, IndexError):
        return render_template(
            "error.html", message="This game is unavailable or changed during inspection."
        ), 400
    return render_template("capture_game.html", report=result)


@short_mate_game_views.get("/game-samples/captures")
def capture_samples():
    subject = normalize_identity(current_app.config["SUBJECT"])
    if subject is None:
        return render_template("error.html", message="Learner identity is unavailable."), 400
    result = capture_trend_report(database(), subject, current_app.config["PROJECT_ROOT"])
    return render_template("capture_game_trend.html", report=result)


@short_mate_game_views.get("/game-samples/knight-forks")
def fork_samples():
    subject = normalize_identity(current_app.config["SUBJECT"])
    if subject is None:
        return render_template("error.html", message="Learner identity is unavailable."), 400
    result = fork_trend_report(database(), subject, current_app.config["PROJECT_ROOT"])
    return render_template("fork_game_trend.html", report=result)
