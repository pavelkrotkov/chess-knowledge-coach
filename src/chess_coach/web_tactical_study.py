"""Request publication of the exact currently offered private course."""

from pathlib import Path
from types import SimpleNamespace

from flask import abort, current_app, redirect, request, url_for

from .tactical_study_request import enqueue


def submit():
    version = request.form.get("version", "")
    db = SimpleNamespace(path=Path(current_app.config["DB_PATH"]))
    part = None
    number = request.form.get("part")
    if number is not None:
        if not number.isascii() or not number.isdecimal() or len(number) > 4:
            abort(400)
        part = {
            "number": int(number),
            "sha256": request.form.get("part_sha256", ""),
            "manifest_sha256": request.form.get("manifest_sha256", ""),
        }
    try:
        enqueue(
            db,
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            current_app.config["CORPUS"],
            version,
            **({"part": part} if part is not None else {}),
        )
    except (OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError):
        abort(409, "This course request is unavailable. Reopen the prepared course.")
    return redirect(url_for("tactical_course_views.show", version=version), code=303)
