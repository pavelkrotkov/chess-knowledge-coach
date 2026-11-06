"""Render the explicit, optionally source-scoped verified capture finder."""

import sqlite3

from flask import current_app, render_template, request

from .capture_finder_scope import option
from .web_board import board_rows
from .web_db import database


def page():
    from .capture_finder import find

    try:
        found = find(
            database(),
            current_app.config["SUBJECT"],
            current_app.config["CORPUS"],
            current_app.secret_key,
            **option(request.args.get("position")),
        )
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        found = None
    if found is None:
        return render_template("capture_finder_empty.html")
    position, result = found
    for item in result["items"]:
        item["board"] = board_rows(item["fen"])
    return render_template("related_capture.html", result=result, position=position)
