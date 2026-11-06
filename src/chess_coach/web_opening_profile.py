"""Show ordered public geometry samples for one current owned decision."""

from flask import Blueprint, abort, current_app, render_template, request

from .opening_decision import inspect
from .opening_explore_enrich import comparison
from .opening_profile_read import profile
from .web_db import database

opening_profiles = Blueprint("opening_profiles", __name__)


def _alternative(items, selected):
    if selected is None:
        return items[0] if items else None
    alternative = next((item for item in items if item["uci"] == selected), None)
    if alternative is None:
        abort(404)
    return alternative


@opening_profiles.get("/repertoire/games/<int:game_id>/openings/<int:position_id>/profile")
def show(game_id: int, position_id: int):
    db = database()
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    try:
        decision = inspect(db, game_id, position_id, current_app.config["SUBJECT"])
    except ValueError:
        abort(404)
    root, subject = current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"]
    parent = decision["catalog"]["parent"]
    played = profile(root, subject, parent, decision["played_uci"])
    items = decision["catalog"]["items"]
    selected = request.args.get("alternative")
    alternative = _alternative(items, selected)
    other = profile(root, subject, parent, alternative["uci"]) if alternative else None
    measured = comparison(db, root, subject, decision, alternative) if alternative else None
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        abort(409)
    return render_template(
        "opening_profile.html",
        decision=decision,
        played=played,
        alternative=alternative,
        selected=selected is not None,
        other=other,
        measured=measured,
    )
