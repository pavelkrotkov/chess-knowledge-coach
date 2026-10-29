"""Constrain snapshot versions to project-local paths."""

import re
import uuid
from pathlib import Path

from .puzzle_snapshot_boundary import checked_path


def version_dir(root, version):
    root = Path(root).resolve(strict=True)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", version) or version in {".", ".."}:
        raise ValueError("version must be a simple unique name")
    path = root / "puzzle-snapshots" / version
    checked_path(path, root)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def new_attempt(path):
    attempt = path / ("attempt-" + uuid.uuid4().hex)
    attempt.mkdir(mode=0o700)
    return attempt


def existing_attempts(base):
    """Enumerate progress without following version or attempt symlinks."""
    root = base.parent
    checked_path(base, root)
    if not base.is_dir():
        return
    for version in base.iterdir():
        checked_path(version, root)
        if not version.is_dir():
            continue
        for attempt in version.glob("attempt-*"):
            checked_path(attempt, root)
            if attempt.is_dir():
                yield attempt
