"""Install and verify a frozen release in its own environment."""

import os
import subprocess
import sys
from pathlib import Path

from .ops_paths import private_directory


def install_release(source: Path, release: Path, runtime: Path) -> None:
    environment = _environment(runtime, release)
    _install(source, environment)
    _verify(release, runtime)


def _environment(runtime: Path, release: Path) -> dict[str, str]:
    cache = private_directory(runtime / "cache", create=True)
    tmp = private_directory(runtime / "tmp", create=True)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "UV_PROJECT_ENVIRONMENT": str(release / "venv"),
            "UV_CACHE_DIR": str(cache / "uv"),
            "XDG_CACHE_HOME": str(cache),
            "TMPDIR": str(tmp),
            "UV_PYTHON": sys.executable,
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_LINK_MODE": "copy",
        }
    )
    return environment


def _install(source: Path, environment: dict[str, str]) -> None:
    subprocess.run(
        ["uv", "sync", "--frozen", "--no-dev", "--no-editable"],
        cwd=source,
        env=environment,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _verify(release: Path, runtime: Path) -> None:
    script = (
        "from importlib.resources import files; import chess_coach; "
        "from pathlib import Path; import sys; "
        "assert Path(chess_coach.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); "
        "assert files('chess_coach').joinpath('templates/practice.html').is_file(); "
        "assert files('chess_coach').joinpath('static/coach.css').is_file()"
    )
    subprocess.run(
        [str(release / "venv/bin/python"), "-I", "-c", script],
        cwd=runtime,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
