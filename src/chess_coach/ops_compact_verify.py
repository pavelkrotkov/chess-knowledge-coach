"""Verify a compact release resolves its own code and the sealed dependencies."""

from .ops_diagnostics import run_checked
from .ops_private_env import environment_and_secrets

MODULES = (
    "berserk",
    "chess",
    "httpx",
    "yaml",
    "pydantic",
    "sqlalchemy",
    "fsrs",
    "flask",
    "waitress",
)


def _script(source, site):
    return (
        "import importlib; from importlib.resources import files; from pathlib import Path; "
        "import chess_coach; "
        f"source=Path({str(source)!r}).resolve(); site=Path({str(site)!r}).resolve(); "
        "assert Path(chess_coach.__file__).resolve().is_relative_to(source), 'module outside source'; "
        f"modules={MODULES!r}; "
        "assert all(Path(importlib.import_module(name).__file__).resolve().is_relative_to(site) "
        "for name in modules), 'dependency outside base'; "
        "services=('chess_coach.web_server','chess_coach.ops_worker','chess_coach.ops_retry'); "
        "assert all(Path(importlib.import_module(name).__file__).resolve().is_relative_to(source) "
        "for name in services), 'service outside source'; "
        "assert files('chess_coach').joinpath('templates/practice.html').is_file(); "
        "assert files('chess_coach').joinpath('templates/board.html').is_file(); "
        "assert files('chess_coach').joinpath('templates/practice_move_form.html').is_file(); "
        "assert files('chess_coach').joinpath('templates/practice_navigation.html').is_file(); "
        "assert files('chess_coach').joinpath('templates/practice_reveal.html').is_file(); "
        "assert files('chess_coach').joinpath('static/coach.css').is_file(); "
        "assert files('chess_coach').joinpath('static/board.js').is_file()"
    )


def verify(release, runtime, site):
    environment, secrets = environment_and_secrets()
    run_checked(
        [str(release / "venv/bin/python"), "-I", "-B", "-c", _script(release / "source/src", site)],
        cwd=runtime,
        environment=environment,
        release=release,
        stage="verification",
        secrets=secrets,
    )
    run_checked(
        [str(release / "venv/bin/chess-coach"), "--help"],
        cwd=runtime,
        environment=environment,
        release=release,
        stage="verification",
        secrets=secrets,
    )


def verify_identity(release, runtime, commit):
    environment, secrets = environment_and_secrets()
    script = (
        "from chess_coach.web_release import release_info; "
        f"info=release_info(); assert info and info['commit']=={commit!r}, "
        "'compact release identity unavailable'"
    )
    run_checked(
        [str(release / "venv/bin/python"), "-I", "-B", "-c", script],
        cwd=runtime,
        environment=environment,
        release=release,
        stage="verification",
        secrets=secrets,
    )
