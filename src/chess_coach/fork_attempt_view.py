"""Serve private bounded fork-attempt history."""

import sqlite3

from flask import current_app, render_template, request

from .fork_attempt_page import page
from .web_db import database


def show():
    try:
        result = page(
            database(),
            current_app.config["SUBJECT"],
            current_app.config["CORPUS"],
            current_app.secret_key,
            request.args.get("cursor"),
        )
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return render_template("error.html", message="Fork attempt history is unavailable."), 400
    return render_template("fork_attempts.html", report=result)
