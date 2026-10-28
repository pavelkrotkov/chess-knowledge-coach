"""Report the installed release identity without trusting a mutable pointer."""

import re
import sys
from pathlib import Path


def release_info() -> dict | None:
    environment = Path(sys.prefix).resolve()
    release = environment.parent
    module = Path(__file__).resolve()
    if not _valid_layout(environment, release, module):
        return None
    try:
        commit = (release / "COMMIT").read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return None
    if commit != release.name or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        return None
    return {"commit": commit, "module_path": str(module)}


def _valid_layout(environment: Path, release: Path, module: Path) -> bool:
    return (
        environment.name == "venv"
        and release.parent.name == "releases"
        and release.parent.parent.name == ".runtime"
        and module.is_relative_to(environment)
    )
