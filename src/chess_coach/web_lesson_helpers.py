"""Render historical coaching previews and standalone lessons."""

from flask import render_template

from .coaching_practice import choices
from .coaching_report import VERSION
from .web_board import board_rows


def display(record, db, subject):
    if record["lesson"].get("kind") == VERSION:
        return render_template(
            "coaching.html",
            preview=record["lesson"],
            record=record,
            board_rows=board_rows,
            practice=choices(db, subject, record["lesson"]),
        )
    return render_template("lesson_history.html", record=record)


def selected(data, form):
    period = form.get("period")
    if period not in {"current", "previous"}:
        return None
    for group in data[period]:
        if all(group[key] == form.get(key) for key in ("skill", "operation", "family", "version")):
            return group
    return None
