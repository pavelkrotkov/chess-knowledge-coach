"""Private discovered-mate transfer preview and assessment admission."""

import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .web_board import board_rows
from .web_db import database

related_discovery = Blueprint("related_discovery", __name__)


@related_discovery.get("/evidence/<int:evidence_id>/related-discovered-mates")
def discovery(evidence_id):
    from .related_capture import present
    from .related_discovery import error_message
    from .related_discovery import selection as discovery_selection

    try:
        result = present(
            discovery_selection(
                database(), current_app.config["SUBJECT"], evidence_id, current_app.config["CORPUS"]
            ),
            request.args.get("cursor"),
        )
        for item in result["items"]:
            item["board"] = board_rows(item["fen"])
    except ValueError as error:
        message = error_message(error, "This discovered-mate source is unavailable.")
        return render_template("error.html", message=message), 400
    return render_template("related_discovery_mate.html", result=result, evidence_id=evidence_id)


@related_discovery.post("/evidence/<int:evidence_id>/related-discovered-mates/start")
def begin_discovery(evidence_id):
    from .related_discovery import error_message
    from .related_discovery_start import start_related as start_discovery

    attempt = secrets.token_urlsafe(24)
    try:
        start_discovery(
            database(),
            attempt_id=attempt,
            subject=current_app.config["SUBJECT"],
            evidence_id=evidence_id,
            corpus_version=current_app.config["CORPUS"],
            reference=request.form.get("reference", ""),
        )
    except ValueError as error:
        message = error_message(error, "This discovered-mate example is unavailable or changed.")
        return render_template("error.html", message=message), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)
