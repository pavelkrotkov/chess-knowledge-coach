"""Open one SQLite connection per browser request."""

from flask import abort, current_app, g, session

from .db import Database


def database() -> Database:
    if "db" not in g:
        g.db = Database(current_app.config["DB_PATH"])
    return g.db


def current_training():
    attempt = session.get("attempt")
    item_id = session.get("item_id")
    if not isinstance(attempt, str) or type(item_id) is not int:
        abort(404)
    return attempt, item_id
