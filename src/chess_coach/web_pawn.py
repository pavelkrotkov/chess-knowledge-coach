"""Private read-only pawn-endgame inspection."""

from flask import Blueprint, abort, current_app, render_template, request

from .pawn_inspection import inspect_pawn
from .web_db import database

pawn_views = Blueprint("pawn", __name__)


@pawn_views.get("/decisions/<int:position_id>/pawn")
def detail(position_id: int):
    try:
        result = inspect_pawn(
            database(),
            position_id,
            learner=current_app.config["SUBJECT"],
            expected_fingerprint=request.args.get("source"),
        )
    except ValueError:
        abort(404)
    return render_template("pawn_inspection.html", pawn=result)
