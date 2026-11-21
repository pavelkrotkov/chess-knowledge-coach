"""Reuse the plan's capture check while resolving the optional focus."""

import sqlite3

from flask import current_app


def generation(db):
    try:
        return db.connection.execute("PRAGMA data_version").fetchone()[0]
    except sqlite3.Error:
        return None


def room_after_due(plan):
    if plan.get("scan", {}).get("due_incomplete", True):
        return False
    return sum(item["kind"] != "new" for item in plan["items"]) < 10


def focus(db, result, current_focus):
    if not room_after_due(result) or result.get("capture_status") == "offered":
        return None, None
    version = generation(db)
    options = {}
    if result.get("capture_status") not in {None, "learning_unavailable"}:
        if version is None or version != result.get("capture_generation"):
            return None, version
        options["capture_override"] = result["capture_focus"]
    focus = current_focus(
        db,
        current_app.config["SUBJECT"],
        current_app.config["CORPUS"],
        include_optional=False,
        **options,
    )
    return focus, version
