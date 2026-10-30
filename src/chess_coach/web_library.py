"""Render bounded private library choices."""

from flask import abort, current_app, render_template, request

from .back_rank_practice import list_candidates as back_rank_candidates
from .discovery_practice import list_candidates as discovery_candidates
from .mate_practice import list_candidates as mate_candidates
from .objective_capture_list import candidates as capture_candidates
from .objective_defense_list import candidates as defense_candidates
from .objective_fork_defense_list import candidates as fork_defense_candidates
from .objective_fork_list import candidates as fork_candidates
from .objective_mate_list import candidates as mate_one_candidates
from .objective_pawn_contract import VERSION as PAWN_OBJECTIVE_VERSION
from .objective_pin_list import candidates as pin_candidates
from .objective_pin_prevent_list import candidates as pin_prevent_candidates
from .objective_protection_list import candidates as protection_candidates
from .objective_short_list import candidates as short_mate_candidates
from .pawn_practice_list import list_candidates as list_pawn_candidates
from .public_training_query import library_groups
from .puzzle_import_report import corpus_report
from .unified_library import corpus_choices
from .unified_own_game import list_candidates
from .unified_session_state import recent as recent_unified
from .web_db import database


def render_library():
    try:
        pawn_game = list_pawn_candidates(
            database(), current_app.config["SUBJECT"], before=request.args.get("pawn_before")
        )
    except ValueError:
        abort(400)
    return render_template(
        "library.html",
        own_game=list_candidates(database(), current_app.config["SUBJECT"]),
        discovery_game=discovery_candidates(database(), current_app.config["SUBJECT"]),
        mate_one_game=mate_one_candidates(database(), current_app.config["SUBJECT"]),
        fork_game=fork_candidates(database(), current_app.config["SUBJECT"]),
        fork_defense_game=fork_defense_candidates(database(), current_app.config["SUBJECT"]),
        pin_game=pin_candidates(database(), current_app.config["SUBJECT"]),
        pin_prevent_game=pin_prevent_candidates(database(), current_app.config["SUBJECT"]),
        protection_game=protection_candidates(database(), current_app.config["SUBJECT"]),
        capture_game=capture_candidates(database(), current_app.config["SUBJECT"]),
        defense_game=defense_candidates(database(), current_app.config["SUBJECT"]),
        short_mate_game=short_mate_candidates(database(), current_app.config["SUBJECT"]),
        mate_game=mate_candidates(database(), current_app.config["SUBJECT"]),
        pawn_game=pawn_game,
        pawn_objective_version=PAWN_OBJECTIVE_VERSION,
        pawn_before=request.args.get("pawn_before"),
        back_rank_game=back_rank_candidates(database(), current_app.config["SUBJECT"]),
        corpora=corpus_choices(database(), corpus_report(database())),
        public_collections=library_groups(database()),
        recent_attempts=recent_unified(database(), current_app.config["SUBJECT"]),
    )
