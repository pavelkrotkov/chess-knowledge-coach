"""Show ordered public geometry samples for one current owned decision."""

from flask import Blueprint, abort, current_app, render_template, request

from .opening_decision import inspect
from .opening_explore_comparison import comparison
from .opening_profile_source import deadline as profile_deadline
from .opening_profile_source import profile
from .opening_public_proof_read import lookup as prepared_proof
from .web_db import database

opening_profiles = Blueprint("opening_profiles", __name__)


def _alternative(items, selected):
    if selected is None:
        return items[0] if items else None
    alternative = next((item for item in items if item["uci"] == selected), None)
    if alternative is None:
        abort(404)
    return alternative


def _reference_options():
    reference = request.args.get("reference", "broadcast")
    fork_window = request.args.get("fork_window", "initial")
    proof_kind = request.args.get("proof_kind", "fork")
    if (
        reference not in {"broadcast", "recent"}
        or fork_window not in {"initial", "continuation"}
        or proof_kind
        not in {
            "fork",
            "prevention",
            "protection",
            "capture_pv",
            "defense_pv",
            "mate",
            "short_mate",
            "back_rank",
            "skewer",
            "double_mate",
        }
    ):
        abort(400)
    return reference, fork_window, proof_kind


@opening_profiles.get("/repertoire/games/<int:game_id>/openings/<int:position_id>/profile")
def show(game_id: int, position_id: int):
    db = database()
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    selected = request.args.get("alternative")
    try:
        decision = inspect(
            db, game_id, position_id, current_app.config["SUBJECT"], alternative=selected
        )
    except ValueError:
        abort(404)
    root, subject = current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"]
    reference, fork_window, proof_kind = _reference_options()
    deadline = profile_deadline(reference)
    played = profile(db, root, subject, decision, decision["played_uci"], reference, deadline)
    items = decision["catalog"]["items"]
    alternative = _alternative(items, selected)
    other = (
        profile(db, root, subject, decision, alternative["uci"], reference, deadline)
        if alternative
        else None
    )
    measured = comparison(db, root, subject, decision, alternative) if alternative else None
    # This request reads a prior preparation; it never runs the capture judge.
    prepared = (
        prepared_proof(
            db,
            root,
            subject,
            game_id,
            position_id,
            alternative["uci"],
            deadline,
            fork_window=fork_window,
            proof_kind=proof_kind,
        )
        if alternative and reference == "recent"
        else None
    )
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
        prepared=prepared,
        reference=reference,
        fork_window=fork_window,
        proof_kind=proof_kind,
    )
