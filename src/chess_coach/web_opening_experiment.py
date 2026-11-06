"""Private read-only opening experiment and PGN download."""

from flask import Blueprint, Response, abort, current_app, render_template, request, url_for

from .opening_experiment_current import current
from .opening_experiment_export import pgn
from .tactical_course_deadline import PreviewDeadline
from .web_board import board_rows
from .web_db import database

opening_experiments = Blueprint("opening_experiments", __name__)


@opening_experiments.get(
    "/repertoire/games/<int:game_id>/openings/<int:position_id>/experiment/<move>"
)
def show(game_id, position_id, move):
    db = database()
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    try:
        decision, choice, experiment = current(
            db,
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            game_id,
            position_id,
            move,
        )
        document = (
            pgn(decision, choice, experiment) if request.args.get("download") == "1" else None
        )
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("opening experiment changed")
    except (Exception, PreviewDeadline):
        abort(404)
    if document is not None:
        return Response(
            document,
            mimetype="application/x-chess-pgn",
            headers={
                "Content-Disposition": 'attachment; filename="opening-experiment.pgn"',
                "Cache-Control": "private, no-store",
            },
        )
    return render_template(
        "opening_experiment.html",
        decision=decision,
        choice=choice,
        experiment=experiment,
        board=board_rows(decision["fen"], decision["color"]),
        download_url=url_for(
            "opening_experiments.show",
            game_id=game_id,
            position_id=position_id,
            move=move,
            download=1,
        ),
    )
