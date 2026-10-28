"""Run the existing bounded worker with a project-contained database."""

import os
import sys
from pathlib import Path

from .cli import main as cli_main
from .web_paths import inside


def database_path() -> Path:
    root = Path(os.environ["CHESS_PROJECT_ROOT"]).resolve(strict=True)
    if root != _release_root():
        raise ValueError("worker project root does not match its installed release")
    data = (root / ".runtime" / "data").resolve(strict=True)
    if not data.is_relative_to(root):
        raise ValueError("worker data directory must be within the selected project")
    database = inside(data, os.environ["CHESS_DB"], existing=True)
    return database


def main() -> None:
    sys.argv = ["chess-coach", "--db", str(database_path()), "process-pipeline"]
    cli_main()


def _release_root() -> Path:
    release = Path(sys.prefix).resolve().parent
    if release.parent.name != "releases" or release.parent.parent.name != ".runtime":
        raise ValueError("worker must use a prepared release environment")
    if (release / "COMMIT").read_text().strip() != release.name:
        raise ValueError("worker release marker does not match its path")
    return release.parent.parent.parent


if __name__ == "__main__":
    main()
