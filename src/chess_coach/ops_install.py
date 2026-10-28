"""Install and verify a frozen release in its own environment."""

import sys
from pathlib import Path

from .ops_diagnostics import run_checked
from .ops_paths import private_directory
from .ops_private_env import environment_and_secrets


def install_release(source: Path, release: Path, runtime: Path) -> None:
    environment, secrets = environment_and_secrets()
    environment.update(_environment(runtime, release))
    _install(source, environment, release, secrets)
    _verify(release, runtime, environment, secrets)


def _environment(runtime: Path, release: Path) -> dict[str, str]:
    cache = private_directory(runtime / "cache", create=True)
    tmp = private_directory(runtime / "tmp", create=True)
    return {
        "UV_PROJECT_ENVIRONMENT": str(release / "venv"),
        "UV_CACHE_DIR": str(cache / "uv"),
        "XDG_CACHE_HOME": str(cache),
        "TMPDIR": str(tmp),
        "UV_PYTHON": sys.executable,
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_LINK_MODE": "copy",
    }


def _install(
    source: Path, environment: dict[str, str], release: Path, secrets: list[bytes]
) -> None:
    run_checked(
        ["uv", "sync", "--frozen", "--no-dev", "--no-editable"],
        cwd=source,
        environment=environment,
        release=release,
        stage="installation",
        secrets=secrets,
    )


def _verify(
    release: Path, runtime: Path, environment: dict[str, str], secrets: list[bytes]
) -> None:
    script = (
        "from importlib.resources import files; import chess_coach; "
        "from pathlib import Path; import sys; "
        "assert Path(chess_coach.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), 'module outside release'; "
        "assert files('chess_coach').joinpath('templates/practice.html').is_file(), 'missing practice template'; "
        "assert files('chess_coach').joinpath('static/coach.css').is_file(), 'missing stylesheet'"
    )
    run_checked(
        [str(release / "venv/bin/python"), "-I", "-B", "-c", script],
        cwd=runtime,
        environment=environment,
        release=release,
        stage="verification",
        secrets=secrets,
    )
