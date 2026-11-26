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
    options = _overrides(result, version)
    if options is None:
        return None, version
    focus = current_focus(
        db,
        current_app.config["SUBJECT"],
        current_app.config["CORPUS"],
        include_optional=False,
        **options,
    )
    return (None if _duplicate(focus, result) else focus), version


def _duplicate(focus, result):
    if not focus or focus.get("selected") != "fork" or not focus.get("fork"):
        return False
    evidence = focus["fork"]["source"]["evidence_id"]
    return any(item.get("source_evidence_id") == evidence for item in result["items"])


def _overrides(result, version):
    # Reuse only checks from the same database generation.
    options = {}
    if result.get("capture_status") not in {None, "learning_unavailable"}:
        if version is None or version != result.get("capture_generation"):
            return None
        options["capture_override"] = (
            None if result["capture_status"] == "history_unavailable" else result["capture_focus"]
        )
    if not _fork_override(result, version, options):
        return None
    return options


def _fork_override(result, version, options):
    if "fork_status" not in result or result["fork_status"] == "learning_unavailable":
        return True
    if result["fork_status"] is not None and (
        version is None or version != result.get("fork_generation")
    ):
        return False
    options["fork_override"] = result.get("fork_focus")
    return True
