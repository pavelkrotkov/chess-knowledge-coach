"""Constrain snapshot versions to project-local paths."""

import re
import uuid
from pathlib import Path


def version_dir(root, version):
    root = Path(root).resolve(strict=True)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", version) or version in {".", ".."}:
        raise ValueError("version must be a simple unique name")
    path = root / "puzzle-snapshots" / version
    if not path.resolve().is_relative_to(root):
        raise ValueError("snapshot must remain inside project root")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def new_attempt(path):
    attempt = path / ("attempt-" + uuid.uuid4().hex)
    attempt.mkdir(mode=0o700)
    return attempt
