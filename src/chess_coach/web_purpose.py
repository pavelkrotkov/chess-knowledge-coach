"""Read-only private candidate-set diagnostic views."""

from flask import Blueprint, current_app, render_template

from .purpose_view import listing, show
from .web_db import database

purpose_views = Blueprint("purpose_views", __name__)


@purpose_views.get("/purpose-analysis")
def index():
    return render_template(
        "purpose_list.html", requests=listing(database(), current_app.config["SUBJECT"])
    )


@purpose_views.get("/purpose-analysis/<int:request_id>")
def detail(request_id):
    try:
        result = show(database(), request_id, current_app.config["SUBJECT"])
    except ValueError:
        return render_template("error.html", message="This diagnostic is unavailable."), 404
    return render_template("purpose_detail.html", result=result)
