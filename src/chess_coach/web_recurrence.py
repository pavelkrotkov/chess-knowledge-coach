"""Private bounded recurring-pattern report."""

from flask import Blueprint, current_app, render_template, request

from .learner_identity import normalize_identity
from .mate_game_trend import report as mate_game_report
from .recurrence_skills import PAIRS
from .recurrence_web_report import landing, selected
from .recurrence_windows import default_windows
from .web_db import database

recurrence_views = Blueprint("recurrence_views", __name__)


def _arguments():
    defaults = default_windows()
    return {
        "start": request.args.get("start") or defaults[0],
        "end": request.args.get("end") or defaults[1],
        "previous": request.args.get("compare_start") or defaults[2],
        "skill": request.args.get("skill") or None,
        "operation": request.args.get("operation") or None,
        "cursor": request.args.get("cursor") or None,
    }


@recurrence_views.get("/recurrence")
def recurrence():
    args = _arguments()
    try:
        db = database()
        subject = normalize_identity(current_app.config["SUBJECT"])
        if any(args[key] for key in ("skill", "operation", "cursor")):
            result, coverage = selected(db, subject, **args), None
        else:
            result = None
            coverage = landing(db, subject, args["start"], args["end"], args["previous"])
        error = None
    except ValueError:
        result, coverage, error = None, None, "Report unavailable; check filters and restart."
    return render_template(
        "recurrence.html", report=result, coverage=coverage, pairs=PAIRS, error=error, **args
    )


@recurrence_views.get("/game-samples/mate-in-one")
def mate_game_samples():
    subject = normalize_identity(current_app.config["SUBJECT"])
    if subject is None:
        return render_template("error.html", message="Learner identity is unavailable."), 400
    result = mate_game_report(database(), subject)
    return render_template("mate_game_trend.html", report=result)
