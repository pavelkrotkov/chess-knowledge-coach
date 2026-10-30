"""Preview and start source-bound protection practice in the browser."""

import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .related_protection import preview
from .related_protection_start import start_related
from .web_board import board_rows
from .web_db import database

related_protection = Blueprint("related_protection", __name__)


@related_protection.get("/evidence/<int:evidence_id>/related-protections")
def show(evidence_id):
    try:
        result = preview(
            database(),
            current_app.config["SUBJECT"],
            evidence_id,
            current_app.config["CORPUS"],
            request.args.get("cursor"),
        )
        for item in result["items"]:
            item["board"] = board_rows(item["fen"])
    except ValueError:
        return render_template(
            "error.html",
            message="This protection source is unsupported, unavailable, or changed. Return to the evidence.",
        ), 400
    return render_template("related_protection.html", result=result, evidence_id=evidence_id)


@related_protection.post("/evidence/<int:evidence_id>/related-protections/start")
def begin(evidence_id):
    attempt = secrets.token_urlsafe(24)
    try:
        start_related(
            database(),
            attempt_id=attempt,
            subject=current_app.config["SUBJECT"],
            evidence_id=evidence_id,
            corpus_version=current_app.config["CORPUS"],
            reference=request.form.get("reference", ""),
        )
    except ValueError:
        return render_template(
            "error.html",
            message="This protection preview is unavailable or changed. Return to the evidence.",
        ), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)
