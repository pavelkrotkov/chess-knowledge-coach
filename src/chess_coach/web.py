"""Create a private browser application over the existing domain services."""

import secrets
from pathlib import Path

from flask import Flask, g

from .web_config import validate_config
from .web_lesson_history import lesson_history_views
from .web_lessons import lesson_views
from .web_mate import mate_views
from .web_pawn import pawn_views
from .web_practice import practice
from .web_practice_tools import practice_tools
from .web_probes import probe_views
from .web_purpose import purpose_views
from .web_recurrence import recurrence_views
from .web_related_capture import related_capture
from .web_related_fork import related_fork
from .web_related_fork_prevention import related_fork_prevention
from .web_related_protection import related_protection
from .web_repertoire import repertoire_views
from .web_security import install_security
from .web_style import style_views
from .web_unified_practice import unified_practice
from .web_views import views


def create_app(
    *,
    db_path: str | Path,
    subject: str,
    actor: str,
    corpus: str,
    login: str,
    origin: str,
    backend_host: str | None = None,
    project_root: str | Path | None = None,
) -> Flask:
    host = validate_config(subject, actor, corpus, login, origin)
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_bytes(32),
        SESSION_COOKIE_NAME="__Host-chess_coach_session",
        SESSION_COOKIE_PATH="/",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        MAX_CONTENT_LENGTH=16384,
        DB_PATH=str(db_path),
        PROJECT_ROOT=str(project_root) if project_root is not None else None,
        SUBJECT=subject,
        ACTOR=actor,
        CORPUS=corpus,
    )
    install_security(app, login, origin, host if backend_host is None else backend_host)
    app.register_blueprint(related_capture)
    app.register_blueprint(related_fork)
    app.register_blueprint(related_fork_prevention)
    app.register_blueprint(related_protection)
    app.register_blueprint(views)
    app.register_blueprint(lesson_views)
    app.register_blueprint(lesson_history_views)
    app.register_blueprint(mate_views)
    app.register_blueprint(pawn_views)
    app.register_blueprint(practice)
    app.register_blueprint(probe_views)
    app.register_blueprint(purpose_views)
    app.register_blueprint(practice_tools)
    app.register_blueprint(unified_practice)
    app.register_blueprint(repertoire_views)
    app.register_blueprint(recurrence_views)
    app.register_blueprint(style_views)

    @app.teardown_appcontext
    def close_database(error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    return app
