"""Read status and evidence and record explicit human reviews."""

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from .capabilities import capability_report
from .competency_coverage import competency_report
from .curriculum import daily_plan
from .decision_inspection import inspect_decision
from .deep_selection_views import list_selections, show_selection
from .evidence_review import inspect_evidence, list_evidence, review_evidence
from .named_structure_report import structure_report
from .named_structure_source import source_position
from .named_structures import VERSION, VERSIONS
from .pipeline_status import pipeline_status
from .public_training_query import library_groups
from .puzzle_import_report import corpus_report
from .puzzle_snapshot_state import statuses
from .unified_library import corpus_choices
from .unified_session_state import recent as recent_unified
from .web_board import board_rows
from .web_db import database
from .web_release import release_info

views = Blueprint("views", __name__)


@views.get("/")
def index():
    return render_template(
        "status.html",
        status=pipeline_status(database(), current_app.config["SUBJECT"]),
        release=release_info(),
        acquisitions=statuses(current_app.config["PROJECT_ROOT"])
        if current_app.config["PROJECT_ROOT"]
        else [],
    )


@views.get("/evidence")
def evidence_list():
    try:
        after = int(request.args.get("after", "0"))
        rows = list_evidence(database(), after_id=after, limit=100)
    except ValueError:
        abort(400)
    return render_template("evidence_list.html", rows=rows)


@views.get("/evidence/<int:evidence_id>")
def evidence_detail(evidence_id: int):
    try:
        evidence = inspect_evidence(database(), evidence_id)
    except ValueError:
        abort(404)
    return render_template(
        "evidence.html", evidence=evidence, board=board_rows(evidence["decision_fen"])
    )


@views.post("/evidence/<int:evidence_id>/review")
def evidence_review(evidence_id: int):
    try:
        review_evidence(
            database(),
            evidence_id,
            decision=request.form.get("decision", ""),
            actor=current_app.config["ACTOR"],
        )
    except ValueError:
        abort(400)
    return redirect(url_for("views.evidence_detail", evidence_id=evidence_id), code=303)


@views.get("/plan")
def plan():
    try:
        result = daily_plan(
            database(),
            subject=current_app.config["SUBJECT"],
            corpus_version=current_app.config["CORPUS"],
            cursor=request.args.get("cursor"),
        )
    except ValueError:
        return render_template(
            "plan.html", error="The plan changed. Restart planning.", plan=None
        ), 400
    return render_template("plan.html", plan=result, error=None)


@views.get("/capabilities")
def capabilities():
    return render_template("capabilities.html", report=capability_report())


@views.get("/decisions/<int:position_id>")
def decision_detail(position_id: int):
    try:
        run_id = request.args.get("run_id")
        result = inspect_decision(
            database(),
            position_id,
            run_id=int(run_id) if run_id else None,
            learner=current_app.config["SUBJECT"],
        )
    except ValueError:
        abort(404)
    return render_template(
        "decision.html", decision=result, board=board_rows(result["decision_fen"])
    )


@views.get("/competencies")
def competencies():
    return render_template("competencies.html", report=competency_report())


@views.get("/deep-selections")
def deep_selections():
    return render_template(
        "deep_selections.html",
        selections=list_selections(database(), current_app.config["SUBJECT"]),
    )


@views.get("/deep-selections/<int:game_id>")
def deep_selection_detail(game_id: int):
    try:
        selection_id = request.args.get("selection")
        result = show_selection(
            database(),
            game_id,
            current_app.config["SUBJECT"],
            selection_id=int(selection_id) if selection_id else None,
        )
    except ValueError:
        abort(404)
    return render_template("deep_selection.html", selection=result)


@views.get("/library")
def library():
    return render_template(
        "library.html",
        corpora=corpus_choices(database(), corpus_report(database())),
        public_collections=library_groups(database()),
        recent_attempts=recent_unified(database(), current_app.config["SUBJECT"]),
    )


@views.get("/structures")
def structures():
    version = request.args.get("version", VERSION)
    if version not in VERSIONS:
        abort(400)
    try:
        report = structure_report(database(), current_app.config["SUBJECT"], version=version)
    except ValueError:
        report = None
    return render_template("structures.html", report=report)


@views.get("/structures/positions/<int:position_id>")
def structure_position(position_id: int):
    try:
        position = source_position(database(), current_app.config["SUBJECT"], position_id)
    except ValueError:
        abort(404)
    return render_template(
        "structure_position.html", position=position, board=board_rows(position["fen"])
    )
