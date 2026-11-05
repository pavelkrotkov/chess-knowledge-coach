"""Preview and start explicitly selected mate transfers in the private browser."""

import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .related_mate import preview
from .related_mate_search_page import preview as search_preview
from .related_mate_search_token import decode
from .related_mate_start import start_related
from .web_board import board_rows
from .web_db import database

related_mate = Blueprint("related_mate", __name__)


@related_mate.get("/evidence/<int:evidence_id>/related-mates")
def show(evidence_id):
    try:
        token = request.args.get("search")
        if token is None:
            result = preview(
                database(),
                current_app.config["SUBJECT"],
                evidence_id,
                current_app.config["CORPUS"],
                request.args.get("cursor"),
            )
        else:
            result = search_preview(
                database(),
                current_app.config["SUBJECT"],
                evidence_id,
                current_app.config["CORPUS"],
                token,
                current_app.secret_key,
            )
        for item in result["items"]:
            item["board"] = board_rows(item["fen"])
    except ValueError:
        message = (
            "This search changed or expired. Return to the evidence and restart."
            if request.args.get("search") is not None
            else "This mate source is unsupported, unavailable, or changed. Return to the evidence."
        )
        return render_template("error.html", message=message), 400
    return render_template("related_mate.html", result=result, evidence_id=evidence_id)


@related_mate.post("/evidence/<int:evidence_id>/related-mates/start")
def begin(evidence_id):
    attempt = secrets.token_urlsafe(24)
    try:
        token = request.form.get("search")
        search_state = decode(current_app.secret_key, token) if token else None
        start_related(
            database(),
            attempt_id=attempt,
            subject=current_app.config["SUBJECT"],
            evidence_id=evidence_id,
            corpus_version=current_app.config["CORPUS"],
            reference=request.form.get("reference", ""),
            assessment=request.form.get("assessment") == "1",
            search_state=search_state,
            search_secret=current_app.secret_key,
        )
    except ValueError:
        return render_template(
            "error.html",
            message="This assessment is unavailable or changed; the bounded proof may not have completed.",
            back_url=url_for("related_mate.show", evidence_id=evidence_id),
            back_label="Return to examples and try the supplied line",
        ), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)
