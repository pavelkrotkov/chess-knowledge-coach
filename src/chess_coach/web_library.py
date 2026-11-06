"""Render the private library without loading owned practice families."""

from flask import current_app, render_template, request

from .public_training_query import library_groups
from .puzzle_import_report import corpus_report
from .unified_library import corpus_choices
from .unified_session_state import recent as recent_unified
from .web_db import database
from .web_library_owned import links
from .web_library_owned import render as render_owned


def render_library():
    family = request.args.get("family")
    before = request.args.get("pawn_before")
    if family is None and before is not None:
        family = "pawn"
    if family is not None:
        return render_owned(database(), current_app.config["SUBJECT"], family, before)
    return render_template(
        "library.html",
        owned_families=links(),
        corpora=corpus_choices(database(), corpus_report(database())),
        public_collections=library_groups(database()),
        recent_attempts=recent_unified(database(), current_app.config["SUBJECT"]),
    )
