"""Private source-linked back-rank attack previews."""

import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .recurrence_snapshot import read_snapshot
from .related_backrank_attack import preview
from .related_backrank_source import roots
from .related_backrank_start import start_related
from .web_board import board_rows
from .web_db import database

related_backrank = Blueprint("related_backrank", __name__)


@related_backrank.get("/evidence/<int:evidence_id>/related-backrank-attacks")
def show(evidence_id):
    try:
        with read_snapshot(database()):
            evidence, _, _, choices = roots(database(), current_app.config["SUBJECT"], evidence_id)
            root_move = request.args.get("root")
            result = None
            if root_move:
                result = preview(
                    database(),
                    current_app.config["SUBJECT"],
                    evidence_id,
                    current_app.config["CORPUS"],
                    root_move,
                    request.args.get("cursor"),
                )
                for item in result["items"]:
                    item["board"] = board_rows(item["fen"])
    except (ValueError, TypeError, KeyError, IndexError):
        return render_template(
            "error.html", message="This back-rank source is unavailable or changed."
        ), 400
    return render_template(
        "related_backrank.html",
        evidence_id=evidence_id,
        choices=choices,
        outcome=evidence["outcome"],
        root_move=root_move,
        result=result,
    )


@related_backrank.post("/evidence/<int:evidence_id>/related-backrank-attacks/start")
def begin(evidence_id):
    attempt = secrets.token_urlsafe(24)
    try:
        start_related(
            database(),
            attempt_id=attempt,
            subject=current_app.config["SUBJECT"],
            evidence_id=evidence_id,
            corpus_version=current_app.config["CORPUS"],
            root_move=request.form.get("root", ""),
            reference=request.form.get("reference", ""),
        )
    except (ValueError, TypeError, KeyError, IndexError):
        return render_template(
            "error.html", message="This back-rank preview is unavailable or changed."
        ), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)
