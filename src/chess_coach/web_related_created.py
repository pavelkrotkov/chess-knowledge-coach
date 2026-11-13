"""Private source-bound created-exposure practice."""

import secrets
import sqlite3

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .related_created import preview, start_related
from .web_board import board_rows
from .web_db import database

related_created = Blueprint("related_created", __name__)


@related_created.get("/evidence/<int:evidence_id>/related-created-exposure")
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
    except sqlite3.OperationalError as error:
        return _busy(error)
    except (ValueError, TypeError, KeyError, IndexError):
        return render_template("error.html", message="This source is unavailable or changed."), 400
    return render_template("related_created.html", result=result, evidence_id=evidence_id)


@related_created.post("/evidence/<int:evidence_id>/related-created-exposure/start")
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
    except sqlite3.OperationalError as error:
        return _busy(error)
    except (ValueError, TypeError, KeyError, IndexError):
        return render_template("error.html", message="This preview is unavailable or changed."), 400
    session["unified_attempt"] = attempt
    return redirect(url_for("unified_practice.show_page", attempt=attempt), code=303)


def _busy(error):
    if getattr(error, "sqlite_errorcode", 0) & 0xFF not in {
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    }:
        raise error
    return render_template(
        "error.html", message="The database is busy. Please try again shortly."
    ), 503
