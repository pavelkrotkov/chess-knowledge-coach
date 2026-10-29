"""Render bounded private library choices."""

from flask import current_app, render_template

from .mate_practice import list_candidates as mate_candidates
from .pawn_practice_list import list_candidates as list_pawn_candidates
from .public_training_query import library_groups
from .puzzle_import_report import corpus_report
from .unified_library import corpus_choices
from .unified_own_game import list_candidates
from .unified_session_state import recent as recent_unified
from .web_db import database


def render_library():
    return render_template(
        "library.html",
        own_game=list_candidates(database(), current_app.config["SUBJECT"]),
        mate_game=mate_candidates(database(), current_app.config["SUBJECT"]),
        pawn_game=list_pawn_candidates(database(), current_app.config["SUBJECT"]),
        corpora=corpus_choices(database(), corpus_report(database())),
        public_collections=library_groups(database()),
        recent_attempts=recent_unified(database(), current_app.config["SUBJECT"]),
    )
