"""Private source-bound knight-fork prevention preview and admission."""

import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .related_fork_prevention import preview
from .related_fork_prevention_start import start_related
from .web_board import board_rows
from .web_db import database

related_fork_prevention = Blueprint("related_fork_prevention", __name__)


@related_fork_prevention.get("/evidence/<int:evidence_id>/related-fork-preventions")
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
            message="This anchored knight-fork source is unsupported, unavailable, or changed.",
        ), 400
    return render_template("related_fork_prevention.html", result=result, evidence_id=evidence_id)


@related_fork_prevention.post("/evidence/<int:evidence_id>/related-fork-preventions/start")
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
            "error.html", message="This fork-prevention preview is unavailable or changed."
        ), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)
