"""Resolve the private project planning directory for a learner."""

import os
from pathlib import Path

from .deep_selection_source import learner_key


def planning(root, subject):
    root = Path(root).resolve(strict=True)
    path = (root / ".runtime" / "planning").resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("planning path unavailable")
    info = path.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("planning path unavailable")
    return path, learner_key(subject)
