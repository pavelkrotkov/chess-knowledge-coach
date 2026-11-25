"""Show current exploratory opening contexts without recording learning activity."""

import time

from flask import Response, abort, current_app, render_template, request

from .opening_context_choice import current
from .opening_context_display import decorate
from .opening_context_inventory import SECONDS, inventory
from .opening_context_preview import preview
from .opening_unfamiliar_guard import start
from .tactical_course_deadline import PreviewDeadline
from .web_db import database


def show():
    db = database()
    root, subject = current_app.config["PROJECT_ROOT"], current_app.config["SUBJECT"]
    deadline = time.monotonic() + SECONDS
    try:
        binding = start(db, root, subject)
        report = inventory(db, root, subject, deadline=deadline)
        if report["status"] != "prepared":
            return render_template("opening_contexts.html", report=report), 503
        choice = request.args.get("choice")
        if choice:
            course = preview(report, choice)
            current(db, root, subject, binding, deadline)
            if request.args.get("download") == "1":
                if request.args.get("version") != course["version"]:
                    raise ValueError("opening selection changed")
                return Response(
                    course["chapter"]["pgn"] + "\n",
                    mimetype="application/x-chess-pgn",
                    headers={"Cache-Control": "private, no-store"},
                )
            return render_template("opening_contexts.html", report=report, course=course)
        decorate(report)
        current(db, root, subject, binding, deadline)
        return render_template("opening_contexts.html", report=report)
    except ValueError:
        if request.args.get("choice"):
            abort(409, "The opening selection or its source changed. Open a new preview.")
        return render_template("opening_contexts.html", report={"status": "unavailable"}), 503
    except (Exception, PreviewDeadline):
        return render_template("opening_contexts.html", report={"status": "unavailable"}), 503
