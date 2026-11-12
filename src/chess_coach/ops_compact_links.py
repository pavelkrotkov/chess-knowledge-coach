"""Restrict release symlinks to their sealed tree or the current interpreter."""

import sys
from pathlib import Path


def link(path, base):
    target = path.resolve(strict=True)
    if target.is_relative_to(base):
        return
    is_python = path.parent == base / "venv" / "bin" and path.name.startswith("python")
    if is_python and target == Path(sys.executable).resolve(strict=True):
        return
    raise ValueError("dependency release has an external link")
