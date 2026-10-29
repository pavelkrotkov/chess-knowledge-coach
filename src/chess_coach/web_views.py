"""Read status and evidence and record explicit human reviews."""

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from .capabilities import capability_report
from .competency_coverage import competency_report
from .curriculum import daily_plan
from .decision_inspection import inspect_decision
from .evidence_review import inspect_evidence, list_evidence, review_evidence
from .pipeline_status import pipeline_status
from .web_board import board_rows
from .web_db import database
from .web_release import release_info

views = Blueprint("views", __name__)


@views.get("/")
def index():
    return render_template(
        "status.html", status=pipeline_status(database()), release=release_info()
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
        result = inspect_decision(database(), position_id, run_id=int(run_id) if run_id else None)
    except ValueError:
        abort(404)
    return render_template(
        "decision.html", decision=result, board=board_rows(result["decision_fen"])
    )


@views.get("/competencies")
def competencies():
    return render_template("competencies.html", report=competency_report())
