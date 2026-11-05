"""Private first-encounter short-mate assessment history."""

from flask import Blueprint, current_app, render_template

from .learner_identity import normalize_identity
from .mate_assessment_history import report
from .web_db import database

assessment_history_views = Blueprint("assessment_history_views", __name__)


@assessment_history_views.get("/assessment-history")
def history():
    subject = current_app.config["SUBJECT"]
    if normalize_identity(subject) is None:
        return render_template("error.html", message="Learner identity is unavailable."), 400
    result = report(database(), subject, current_app.config["CORPUS"])
    return render_template("mate_assessment_history.html", report=result)
